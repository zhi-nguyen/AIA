from celery_app import celery_app
import asyncio
from agents.graph import get_compiled_graph
from langchain_core.messages import HumanMessage
import traceback

def get_or_create_eventloop():
    try:
        return asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop

@celery_app.task(bind=True, name="tasks.process_chat")
def process_chat(self, user_id: str, message: str, doc_context: str, image_context: str, image_filename: str):
    try:
        combined_context = doc_context
        if image_context:
            combined_context += f"\n\n[Ảnh đã upload: {image_filename}]\n{image_context}"

        initial_state = {
            "messages": [HumanMessage(content=message)],
            "user_id": user_id,
            "user_context": "",
            "route": "",
            "route_reasoning": "",
            "tool_results": "",
            "final_response": "",
            "document_context": combined_context,
            "error": "",
        }

        loop = get_or_create_eventloop()
        graph = get_compiled_graph()
        result = loop.run_until_complete(graph.ainvoke(initial_state))

        response_payload = {
            "response": result.get("final_response", "Xin lỗi, tôi không thể xử lý yêu cầu này.") or "Xin lỗi, tôi không thể xử lý.",
            "route": result.get("route"),
            "route_reasoning": result.get("route_reasoning"),
        }

        # Publish result back to WebSockets via Redis PubSub
        try:
            import redis
            import json
            from celery_app import redis_url
            r = redis.from_url(redis_url)
            # Attach user_id and task_id to payload so FastAPI knows where to route
            pub_data = {**response_payload, "user_id": user_id, "type": "chat_response", "task_id": self.request.id}
            r.publish("aia_ws_messages", json.dumps(pub_data))
        except Exception as redis_e:
            print(f"[Celery] Redis publish error: {redis_e}")

        return response_payload
    except Exception as e:
        traceback.print_exc()
        raise Exception(f"Chat processing error: {str(e)}")

@celery_app.task(bind=True, name="tasks.generate_tts")
def generate_tts(self, user_id: str, text: str):
    try:
        from services.tts_service import synthesize_speech
        import base64
        import redis
        import json
        from celery_app import redis_url
        
        audio_bytes = synthesize_speech(text)
        base64Str = base64.b64encode(audio_bytes).decode('utf-8')
        
        payload = {
            "type": "tts_response",
            "task_id": self.request.id,
            "user_id": user_id,
            "audio_base64": base64Str
        }
        
        # Publish to WebSocket
        try:
            r = redis.from_url(redis_url)
            r.publish("aia_ws_messages", json.dumps(payload))
        except Exception as redis_e:
            print(f"[Celery] Redis publish error for TTS: {redis_e}")
            
        return {"audio_base64": base64Str}
        
    except Exception as e:
        traceback.print_exc()
        # Publish error so frontend doesn't hang forever
        try:
            import redis
            import json
            from celery_app import redis_url
            r = redis.from_url(redis_url)
            payload = {
                "type": "tts_response",
                "task_id": self.request.id,
                "user_id": user_id,
                "error": str(e)
            }
            r.publish("aia_ws_messages", json.dumps(payload))
        except:
            pass
            
        raise Exception(f"TTS generation error: {str(e)}")


@celery_app.task(bind=True, name="tasks.auto_ingest_news")
def auto_ingest_news(self, user_id: str = "default_user"):
    """
    Periodic task: Tự động thu thập tin tức bằng Gemini + Google Search Grounding,
    dựa trên profile người dùng (đa ngành), sau đó đẩy vào Vertex AI Search data store.
    """
    import uuid
    from llm.gemini_client import get_gemini_client
    from tools.news_tools import parse_gemini_json, push_to_vertex_search
    from memory.user_context import get_user_profile

    # Danh mục tin tức — xây dựng từ profile người dùng
    profile = get_user_profile(user_id)
    categories: list[str] = []

    if profile:
        occupation = profile.get("occupation", "")
        interests = profile.get("interests", [])
        news_sources = profile.get("preferred_news_sources", [])

        # Tạo categories từ sở thích
        for interest in interests:
            categories.append(f"Tin tức mới nhất về {interest}")
        # Thêm category theo nghề nghiệp
        if occupation:
            categories.append(f"Xu hướng và quy định mới trong lĩnh vực {occupation}")
        # Thêm nguồn tin ưa thích
        for src in news_sources:
            categories.append(f"Cập nhật mới nhất về {src}")

    # Fallback: danh mục đa ngành mặc định
    if not categories:
        categories = [
            "Công nghệ AI và ứng dụng thực tiễn",
            "Xu hướng chuyển đổi số doanh nghiệp",
            "Tin tức pháp luật và quy định mới",
            "Kinh tế và thị trường tài chính",
            "Khoa học công nghệ nổi bật",
        ]

    client = get_gemini_client()
    total_pushed = 0
    total_failed = 0

    for cat in categories:
        print(f"\n[AutoIngest] 🔍 Processing category: {cat}")

        prompt = f"""
Sử dụng Google Search để tìm 3 tin tức quan trọng và mới nhất hôm nay về: '{cat}'.
Tóm tắt và trả về dưới dạng JSON array chuẩn:
[
  {{
    "id": "<unique-id>",
    "title": "Tiêu đề bài viết",
    "content": "Tóm tắt nội dung chính (200-400 từ)",
    "metadata": {{
      "domain": "{cat}",
      "tag": "{cat}",
      "source": "Tên nguồn tin",
      "url": "URL gốc nếu có"
    }}
  }}
]

Quy tắc:
- Mỗi "id" phải là unique string (dùng slug từ tiêu đề).
- "content" phải là bản tóm tắt đầy đủ, có giá trị thông tin.
- Chỉ trả về JSON, không thêm text giải thích.
"""

        try:
            response = client.generate_search_grounded(prompt)
            news_data = parse_gemini_json(response)

            if not news_data:
                print(f"[AutoIngest] ⚠️ No valid JSON for category: {cat}")
                continue

            print(f"[AutoIngest] 📰 Found {len(news_data)} articles for: {cat}")

            for news in news_data:
                # Đảm bảo có ID (fallback: UUID)
                if not news.get("id"):
                    news["id"] = str(uuid.uuid4())[:8]

                # Đảm bảo metadata tồn tại
                if "metadata" not in news:
                    news["metadata"] = {"domain": "HIS", "tag": cat}

                success = push_to_vertex_search(news)
                if success:
                    total_pushed += 1
                else:
                    total_failed += 1

        except Exception as e:
            print(f"[AutoIngest] ❌ Error processing category '{cat}': {e}")
            total_failed += 1

    summary = f"[AutoIngest] ✅ Completed: {total_pushed} pushed, {total_failed} failed"
    print(summary)
    return {"pushed": total_pushed, "failed": total_failed}


@celery_app.task(bind=True, name="tasks.generate_user_proposals")
def generate_user_proposals(self, user_id: str = "default_user"):
    """
    Periodic task: Tạo đề xuất hành động dựa trên profile người dùng
    và tin tức từ Vertex AI Search, sau đó push qua WebSocket.
    """
    import redis as redis_lib
    from agents.news_agent import generate_proposal_for_user
    from celery_app import redis_url

    try:
        print(f"\n[ProposalTask] 🚀 Starting proposal generation for user: {user_id}")

        proposal = generate_proposal_for_user(user_id)

        if not proposal:
            print(f"[ProposalTask] ℹ️ No proposal generated for user: {user_id}")
            return {"status": "no_proposal", "user_id": user_id}

        # Push proposal tới frontend qua Redis PubSub
        try:
            r = redis_lib.from_url(redis_url)
            import json
            pub_data = {
                "type": "new_proposal",
                "user_id": user_id,
                "task_id": self.request.id,
                "proposal": proposal,
            }
            r.publish("aia_ws_messages", json.dumps(pub_data, ensure_ascii=False))
            print(f"[ProposalTask] ✅ Proposal pushed to WebSocket: {proposal.get('title', '')[:60]}")
        except Exception as redis_e:
            print(f"[ProposalTask] ❌ Redis publish error: {redis_e}")

        return {"status": "success", "user_id": user_id, "proposal_title": proposal.get("title", "")}

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"[ProposalTask] ❌ Error: {e}")
        return {"status": "error", "error": str(e)}

