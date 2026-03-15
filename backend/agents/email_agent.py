"""
email_agent.py - Email Agent Node
Xử lý các yêu cầu liên quan đến email qua Gmail API
"""

import json
from agents.state import AgentState
from llm.gemini_client import get_gemini_client
from tools.email_tools import (
    fetch_unread_emails,
    summarize_emails,
    check_gmail_configured,
    check_gmail_authorized,
)
from langchain_core.messages import HumanMessage


def email_node(state: AgentState) -> dict:
    """
    Node Email Agent trong LangGraph.
    
    Flow:
    1. Kiểm tra Gmail đã cấu hình chưa
    2. Fetch unread emails
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

    # === Fetch emails ===
    try:
        emails = fetch_unread_emails(limit=5)

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
