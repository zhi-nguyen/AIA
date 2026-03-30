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


# ── Chat task ──────────────────────────────────────────────────────────────
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

        # Publish result back via Redis PubSub
        try:
            import redis
            import json
            from celery_app import redis_url
            r = redis.from_url(redis_url)
            pub_data = {**response_payload, "user_id": user_id, "type": "chat_response", "task_id": self.request.id}
            r.publish("aia_ws_messages", json.dumps(pub_data))
        except Exception as redis_e:
            print(f"[Celery] Redis publish error: {redis_e}")

        return response_payload
    except Exception as e:
        traceback.print_exc()
        raise Exception(f"Chat processing error: {str(e)}")


# ── TTS task ───────────────────────────────────────────────────────────────
@celery_app.task(bind=True, name="tasks.generate_tts")
def generate_tts(self, user_id: str, text: str):
    try:
        from services.tts_service import synthesize_speech
        import base64
        import redis
        import json
        from celery_app import redis_url

        audio_bytes = synthesize_speech(text)
        base64Str = base64.b64encode(audio_bytes).decode("utf-8")

        payload = {
            "type": "tts_response",
            "task_id": self.request.id,
            "user_id": user_id,
            "audio_base64": base64Str,
        }

        try:
            r = redis.from_url(redis_url)
            r.publish("aia_ws_messages", json.dumps(payload))
        except Exception as redis_e:
            print(f"[Celery] Redis publish error for TTS: {redis_e}")

        return {"audio_base64": base64Str}

    except Exception as e:
        traceback.print_exc()
        try:
            import redis
            import json
            from celery_app import redis_url
            r = redis.from_url(redis_url)
            payload = {
                "type": "tts_response",
                "task_id": self.request.id,
                "user_id": user_id,
                "error": str(e),
            }
            r.publish("aia_ws_messages", json.dumps(payload))
        except Exception:
            pass
        raise Exception(f"TTS generation error: {str(e)}")


# ── Email Assistant task (Phase 4 — wraps Phase 2 filter + Phase 3 AI Secretary) ──────────────

@celery_app.task(bind=True, name="tasks.hourly_email_assistant")
def hourly_email_assistant(self):
    """
    Chạy mỗi 30 giây (test environment): quét toàn bộ users đã cấp phép Gmail,
    kéo email mới (Tier 1 DB diff + Tier 2 Regex), rồi gọi
    process_email_intent() cho từng email vượt qua bộ lọc.
    """
    import asyncio
    import traceback

    async def _run():
        from services.db_service import get_all_authorized_users
        from tools.email_tools import fetch_unread_emails, check_gmail_authorized
        from agents.email_agent import process_email_intent

        users = await get_all_authorized_users()
        print(f"[EmailAssistant] Bắt đầu — {len(users)} user(s) đã cấp phép")

        for user_id in users:
            try:
                if not await check_gmail_authorized(user_id):
                    continue

                # fetch_unread_emails đã tích hợp Tier 1 (DB diff) + Tier 2 (Regex)
                emails = await fetch_unread_emails(user_id=user_id, limit=10)
                print(f"[EmailAssistant] user={user_id} → {len(emails)} email qua bộ lọc")

                for email_data in emails:
                    try:
                        await process_email_intent(user_id=user_id, email_data=email_data)
                    except Exception as email_err:
                        print(f"[EmailAssistant] intent error for {email_data.get('id')}: {email_err}")

            except Exception as user_err:
                print(f"[EmailAssistant] Lỗi user={user_id}: {user_err}")
                traceback.print_exc()

        print("[EmailAssistant] Hoàn thành chu kỳ")

    loop = get_or_create_eventloop()
    loop.run_until_complete(_run())

