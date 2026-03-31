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


# ── Email Assistant task (on-demand — triggered by Gmail Watch Pub/Sub) ─────
# Không còn chạy theo Celery Beat. Thay vào đó, gmail_watch.py gọi trực tiếp
# async qua FastAPI event loop khi nhận push notification từ Google Pub/Sub.
# Task Celery này giữ lại như fallback nếu cần gọi thủ công từ CLI/API.

@celery_app.task(bind=True, name="tasks.process_user_emails")
def process_user_emails(self, user_id: str):
    """
    On-demand: Kéo email mới cho MỘT user cụ thể.
    Được gọi khi Gmail Watch Pub/Sub phát hiện email mới,
    hoặc khi admin muốn trigger thủ công.
    """
    import asyncio
    import traceback

    async def _run():
        from tools.email_tools import fetch_unread_emails, check_gmail_authorized
        from agents.email_agent import process_email_intent

        if not await check_gmail_authorized(user_id):
            print(f"[EmailTask] User {user_id[:8]}… chưa cấp phép Gmail")
            return

        emails = await fetch_unread_emails(user_id=user_id, limit=10)
        print(f"[EmailTask] user={user_id[:8]}… → {len(emails)} email qua bộ lọc")

        for email_data in emails:
            try:
                await process_email_intent(user_id=user_id, email_data=email_data)
            except Exception as email_err:
                print(f"[EmailTask] intent error for {email_data.get('id')}: {email_err}")
                traceback.print_exc()

    loop = get_or_create_eventloop()
    loop.run_until_complete(_run())

