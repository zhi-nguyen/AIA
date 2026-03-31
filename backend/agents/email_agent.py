"""
email_agent.py - Email Agent Node
Xử lý các yêu cầu liên quan đến email qua Gmail API.
Phase 3: Bổ sung process_email_intent() — AI Thư Ký phân tích hẹn gặp.
"""

import json
from datetime import datetime, timezone, timedelta
from agents.state import AgentState
from llm.gemini_client import get_gemini_client
from tools.email_tools import (
    fetch_unread_emails,
    summarize_emails,
    check_gmail_configured,
    check_gmail_authorized,
)
from langchain_core.messages import HumanMessage


async def email_node(state: AgentState) -> dict:
    """
    Node Email Agent trong LangGraph.
    
    Flow:
    1. Kiểm tra Gmail đã cấu hình chưa
    2. Fetch unread emails (đã qua Tier 1 + Tier 2 filter)
    3. Tóm tắt bằng Gemini
    4. Trả về response cho user
    """
    client = get_gemini_client()

    # Lấy tin nhắn cuối
    last_message = ""
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage) or (hasattr(msg, "type") and msg.type == "human"):
            last_message = msg.content if hasattr(msg, "content") else str(msg)
            break

    user_id = state.get("user_id", "default_user")

    # === Kiểm tra Gmail configuration ===
    if not check_gmail_configured():
        return {
            "final_response": (
                "**Chưa cấu hình Gmail API**\n\n"
                "Để sử dụng tính năng email, bạn cần:\n"
                "1. Vào [Google Cloud Console](https://console.cloud.google.com/)\n"
                "2. Tạo project mới hoặc chọn project có sẵn\n"
                "3. Enable **Gmail API**\n"
                "4. Tạo **OAuth 2.0 Client ID** (Desktop App)\n"
                "5. Download file `credentials.json` và đặt vào thư mục `backend/`\n\n"
                "Sau đó hãy thử lại nhé!"
            ),
            "tool_results": json.dumps({"status": "not_configured"}),
        }
        
    if not await check_gmail_authorized(user_id):
        return {
            "final_response": "Bạn chưa đăng nhập Google hoặc chưa cấp quyền đọc Gmail. Hãy đăng nhập ở góc dưới màn hình nhé!",
            "tool_results": json.dumps({"status": "not_authorized"}),
        }

    # === Fetch emails ===
    try:
        emails = await fetch_unread_emails(user_id=user_id, limit=5)

        if not emails:
            return {
                "final_response": "Không có email mới nào chưa đọc. Hộp thư sạch sẽ!",
                "tool_results": json.dumps({"status": "no_unread"}),
            }

        # === Tóm tắt emails ===
        summary = summarize_emails(emails)
        email_list = summary.get("emails", [])

        # Format response đẹp
        response_parts = [f"**Bạn có {len(emails)} email chưa đọc:**\n"]

        for i, email_info in enumerate(email_list, 1):
            priority_label = {
                "high": "[Quan trọng]",
                "medium": "[Bình thường]", 
                "low": "[Ít quan trọng]",
            }.get(email_info.get("priority", "medium"), "[Bình thường]")

            response_parts.append(
                f"**{i}. {email_info.get('subject', 'Không có tiêu đề')}** {priority_label}  \n"
                f"Từ: {email_info.get('from', 'Không rõ')}  \n"
                f"Tóm tắt: {email_info.get('summary', 'Không có tóm tắt')}  \n\n"
            )

        # Thêm raw summary nếu có
        if "raw_summary" in summary:
            response_parts.append(f"\n---\n{summary['raw_summary']}")

        return {
            "final_response": "\n".join(response_parts),
            "tool_results": json.dumps(summary, ensure_ascii=False),
        }

    except Exception as e:
        print(f"[EmailAgent] Lỗi: {e}")
        return {
            "final_response": f"Xin lỗi, tôi gặp lỗi khi đọc email: {str(e)}",
            "tool_results": json.dumps({"error": str(e)}),
        }


# ---------------------------------------------------------------------------
# AI Secretary — Meeting Intent Classifier
# ---------------------------------------------------------------------------

async def process_email_intent(user_id: str, email_data: dict) -> dict | None:
    """
    Phase 3: Phân tích một email đã qua Tier 1+2 để xem có phải lời mời hẹn không.

    Pipeline:
        email_data (subject, body, from, …)
            ↓ inject real-time timestamp
        Gemini Flash [response_mime_type="application/json"]
            ↓ guaranteed JSON contract
        WebSocket push → UI (type: "NEW_PROPOSAL")
            ↓
        add_processed_email() → đánh dấu đã xử lý

    Returns:
        dict kết quả phân tích nếu thành công, hoặc None nếu lỗi.
    """
    from llm.prompts import MEETING_INTENT_PROMPT
    from services.db_service import add_processed_email, create_pending_proposal

    client = get_gemini_client()

    # Inject múi giờ +07:00 (Việt Nam)
    vn_tz = timezone(timedelta(hours=7))
    current_time = datetime.now(vn_tz).strftime("%Y-%m-%dT%H:%M:%S+07:00")

    prompt = MEETING_INTENT_PROMPT.format(
        current_time=current_time,
        sender=email_data.get("from", ""),
        subject=email_data.get("subject", ""),
        body=email_data.get("body") or email_data.get("snippet", ""),
    )

    try:
        # Gọi Flash với chế độ JSON bắt buộc — không bao giờ trả về free-text
        raw_json = client.generate_flash(
            prompt=prompt,
            response_mime_type="application/json",
        )

        result: dict = json.loads(raw_json)
        result["gmail_id"] = email_data.get("id", "")
        result["email_subject"] = email_data.get("subject", "")
        result["email_from"] = email_data.get("from", "")

        print(
            f"[EmailAgent][Secretary] gmail_id={result['gmail_id']} | "
            f"is_invitation={result.get('is_invitation')} | "
            f"confidence={result.get('confidence', 0):.2f}"
        )

        # Lưu Proposal vào Database để đồng bộ lâu dài
        if result.get("is_invitation") or result.get("suggested_actions"):
            proposal_id = await create_pending_proposal(user_id, result["gmail_id"], result)
            result["db_id"] = proposal_id
            print(f"[EmailAgent][Secretary] Đã lưu db_id={proposal_id}")

        # Đẩy kết quả lên UI qua Redis PubSub (để FastAPI forward qua WebSocket)
        try:
            import redis.asyncio as aioredis
            from celery_app import redis_url
            r = aioredis.from_url(redis_url)
            pub_data = {
                "type": "NEW_PROPOSAL",
                "source": "email_secretary",
                "user_id": user_id,
                "data": result,
            }
            await r.publish("aia_ws_messages", json.dumps(pub_data, ensure_ascii=False))
            print(f"[EmailAgent][Secretary] Đã push proposal qua Redis PubSub cho user={user_id}")
        except Exception as redis_e:
            print(f"[EmailAgent][Secretary] Redis publish error cho user={user_id}: {redis_e}")

        # Đánh dấu email đã xử lý (dù có gửi WS hay không)
        await add_processed_email(user_id, email_data.get("id", ""))

        return result

    except json.JSONDecodeError as e:
        print(f"[EmailAgent][Secretary] JSON parse error: {e} — raw: {raw_json[:200]}")
        return None
    except Exception as e:
        print(f"[EmailAgent][Secretary] Lỗi xử lý email intent: {e}")
        return None

