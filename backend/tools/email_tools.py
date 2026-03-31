"""
email_tools.py - Gmail API Integration
Kết nối Gmail API qua OAuth2 để đọc và tóm tắt email

Yêu cầu:
1. Tạo OAuth2 credentials trên Google Cloud Console
2. Enable Gmail API
3. Download credentials.json vào thư mục backend/
4. Chạy lần đầu để authorize (tạo token.json)
"""

import os
import re
import json
import base64
from typing import Optional
from email.utils import parsedate_to_datetime
from datetime import datetime

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from llm.gemini_client import get_gemini_client
from llm.prompts import EMAIL_SUMMARY_PROMPT

# Gmail API scopes - gmail.modify bao gồm readonly + send + mark as read/unread
SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]

# Đường dẫn file credentials và token
CREDENTIALS_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "credentials.json")
TOKEN_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "token.json")


async def _get_gmail_service(user_id: str):
    """
    Khởi tạo Gmail API service với OAuth2 từ DB.
    Tự động refresh token nếu hết hạn.
    """
    from services.db_service import get_google_credentials, update_google_credentials
    from services.crypto_service import decrypt_token, encrypt_token
    
    creds_row = await get_google_credentials(user_id)
    if not creds_row or not creds_row.get("encrypted_access_token"):
        raise ValueError("User has no Google credentials")
        
    access_token = decrypt_token(creds_row["encrypted_access_token"])
    refresh_token = decrypt_token(creds_row["encrypted_refresh_token"]) if creds_row.get("encrypted_refresh_token") else None
    
    if not os.path.exists(CREDENTIALS_PATH):
        raise FileNotFoundError(
            f"Không tìm thấy {CREDENTIALS_PATH}. "
            "Hãy lấy từ Google Cloud Console."
        )
        
    with open(CREDENTIALS_PATH, "r") as f:
        client_config = json.load(f).get("web", {})
        
    creds = Credentials(
        token=access_token,
        refresh_token=refresh_token,
        token_uri=client_config.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=client_config.get("client_id"),
        client_secret=client_config.get("client_secret"),
        # Không truyền scopes — Dùng scope đã cấp phép lúc OAuth login ban đầu.
        # Nếu truyền scope khác sẽ gây lỗi invalid_scope khi refresh token.
    )

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        new_enc_access = encrypt_token(creds.token)
        new_enc_refresh = encrypt_token(creds.refresh_token) if creds.refresh_token else creds_row["encrypted_refresh_token"]
        await update_google_credentials(user_id, new_enc_access, new_enc_refresh)

    return build("gmail", "v1", credentials=creds)


def _decode_email_body(payload: dict) -> str:
    """Decode email body từ base64"""
    body = ""

    if "parts" in payload:
        for part in payload["parts"]:
            if part["mimeType"] == "text/plain":
                data = part["body"].get("data", "")
                if data:
                    body = base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
                    break
            elif part["mimeType"] == "text/html" and not body:
                data = part["body"].get("data", "")
                if data:
                    body = base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
    elif payload.get("body", {}).get("data"):
        body = base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")

    return body[:3000]  # Giới hạn 3000 ký tự để tránh quá dài


def _get_header(headers: list, name: str) -> str:
    """Lấy giá trị header từ email"""
    for header in headers:
        if header["name"].lower() == name.lower():
            return header["value"]
    return ""


# ---------------------------------------------------------------------------
# Tier 2 Filter — Zero-Token Regex Gate
# ---------------------------------------------------------------------------

# Từ khóa tiếng Việt và tiếng Anh liên quan đến cuộc hẹn / cuộc họ p
_MEETING_PATTERN = re.compile(
    r"("
    # Tiếng Việt
    r"hẹn|gặp|họ p|hợp|lịch|mời|thời gian|thời điểm"
    r"|buổi|sáng|chiều|tối|mai|ngày mai|tuần tới|lúc nào"
    r"|vào lúc|vào ngày|cuối tuần|cuối tháng|chiều nay|sáng nay|tối nay"
    r"|cuộc hẹn|kế hoạch|thuần tiện|tiện không|có thể gặp"
    # Tiếng Anh
    r"|meeting|schedule|appointment|calendar|invite|invitation"
    r"|call|sync|standup|stand-up|huddle|catch.?up"
    r"|available|availability|free slot|time slot"
    r"|monday|tuesday|wednesday|thursday|friday|saturday|sunday"
    r"|tomorrow|next week|this week|\d{1,2}[:/h]\d{2}"
    r")",
    re.IGNORECASE | re.UNICODE,
)


def is_potential_meeting(subject: str, body: str) -> bool:
    """
    Tier 2 Filter: Kiểm tra nhanh bằng Regex xem email có liên quan
    đến cuộc hẹn / cuộc họ p không.
    Chi phí: 0 token. Chỳ dùng CPU + Regex.

    Returns:
        True  — có thể là email hẹn cần Agent phân tích.
        False — email không liên quan, đánh dấu processed và bỏ qua.
    """
    text_to_scan = f"{subject} {body[:500]}"
    return bool(_MEETING_PATTERN.search(text_to_scan))


async def fetch_unread_emails(user_id: str, limit: int = 10) -> list[dict]:
    """
    Fetch email chưa đọc từ Gmail sau khi áp dụng 2 tầng lọc không tốn token.

    Pipeline:
        [Gmail API - IDs only]
            ↓ Tier 1: DB diff — loại Gmail ID đã xử lý trước đó (0 token)
        [Gmail API - full content]
            ↓ Tier 2: Regex gate — loại email không liên quan hẹn gặp (0 token)
        [Emails passed to Agent]
            → Chỉ email này được gửi đến LLM (tiết kiệm token tối đa)
    """
    from services.db_service import get_processed_email_ids, add_processed_email

    try:
        service = await _get_gmail_service(user_id)

        # ---------------------------------------------------------------
        # Bước 1: Lấy danh sách ID email chưa đọc (chỉ IDs, không lấy nội dung)
        # ---------------------------------------------------------------
        results = service.users().messages().list(
            userId="me",
            q="is:unread",
            maxResults=limit,
        ).execute()

        incoming_ids: list[str] = [
            msg["id"] for msg in results.get("messages", [])
        ]
        if not incoming_ids:
            print("[EmailTools] Không có email chưa đọc mới.")
            return []

        # ---------------------------------------------------------------
        # Tier 1: DB Diff — Loại bỏ ID đã xử lý trước đó (một lần query DB)
        # ---------------------------------------------------------------
        processed_ids: set[str] = await get_processed_email_ids(user_id)
        new_ids = [gid for gid in incoming_ids if gid not in processed_ids]

        print(
            f"[EmailTools][Tier1] Tổng IDs: {len(incoming_ids)} │ "
            f"Mới (chưa xử lý): {len(new_ids)} │ "
            f"Bỏ qua (Tier1): {len(incoming_ids) - len(new_ids)}"
        )

        if not new_ids:
            return []

        # ---------------------------------------------------------------
        # Bước 2: Lấy nội dung đầy đủ chỉ cho các email MỚI
        # ---------------------------------------------------------------
        emails: list[dict] = []
        tier2_skipped = 0

        for gmail_id in new_ids:
            msg = service.users().messages().get(
                userId="me",
                id=gmail_id,
                format="full",
            ).execute()

            headers = msg.get("payload", {}).get("headers", [])
            subject = _get_header(headers, "Subject")
            body    = _decode_email_body(msg.get("payload", {}))
            snippet = msg.get("snippet", "")

            # -----------------------------------------------------------
            # Tier 2: Regex Gate — không liên quan hẹn gặp → bỏ qua
            # -----------------------------------------------------------
            if not is_potential_meeting(subject, body or snippet):
                await add_processed_email(user_id, gmail_id)
                tier2_skipped += 1
                print(
                    f"[EmailTools][Tier2] Bỏ qua (không liên quan hẹn): "
                    f"id={gmail_id} | subject=\"{subject[:60]}\""
                )
                continue

            # Đánh dấu đã xử lý NGAY để tránh duplicate khi Pub/Sub gửi
            # nhiều notification cho cùng một email (at-least-once delivery)
            await add_processed_email(user_id, gmail_id)

            emails.append({
                "id": gmail_id,
                "subject": subject,
                "from": _get_header(headers, "From"),
                "date": _get_header(headers, "Date"),
                "snippet": snippet,
                "body": body,
            })

        print(
            f"[EmailTools] Kết quả: {len(emails)} email đưa vào Agent │ "
            f"Tier2 bỏ qua: {tier2_skipped}"
        )
        return emails

    except FileNotFoundError as e:
        print(f"[EmailTools] {e}")
        return []
    except Exception as e:
        print(f"[EmailTools] Lỗi fetch emails: {e}")
        return []


def summarize_emails(emails: list[dict]) -> dict:
    """
    Tóm tắt danh sách email bằng Gemini.
    
    - Dùng Gemini Flash cho email ngắn
    - Dùng Gemini Pro cho email dài/phức tạp
    
    Returns:
        dict: {"emails": [{"subject": "...", "from": "...", "summary": "...", "priority": "high|medium|low"}]}
    """
    if not emails:
        return {"emails": [], "message": "Không có email mới."}

    client = get_gemini_client()

    # Chuẩn bị email text
    email_text = ""
    total_length = 0
    for i, email in enumerate(emails, 1):
        entry = f"\n--- Email {i} ---\n"
        entry += f"Từ: {email['from']}\n"
        entry += f"Tiêu đề: {email['subject']}\n"
        entry += f"Ngày: {email['date']}\n"
        entry += f"Nội dung: {email.get('body', email.get('snippet', 'Không có nội dung'))}\n"
        email_text += entry
        total_length += len(entry)

    prompt = EMAIL_SUMMARY_PROMPT.format(emails=email_text)

    try:
        # Dùng Pro nếu nội dung nhiều (>2000 chars), Flash nếu ít
        if total_length > 2000:
            response = client.generate_pro(prompt)
        else:
            response = client.generate_flash(prompt)

        # Parse JSON response
        import re
        clean = response.strip()
        if "```" in clean:
            match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", clean, re.DOTALL)
            if match:
                clean = match.group(1).strip()

        try:
            result = json.loads(clean)
            return result
        except json.JSONDecodeError:
            # Fallback: tạo summary đơn giản
            return {
                "emails": [
                    {
                        "subject": e["subject"],
                        "from": e["from"],
                        "summary": e.get("snippet", ""),
                        "priority": "medium",
                    }
                    for e in emails
                ],
                "raw_summary": response,
            }

    except Exception as e:
        print(f"[EmailTools] Lỗi summarize: {e}")
        return {"emails": [], "error": str(e)}

def check_gmail_configured() -> bool:
    """Kiểm tra Gmail API đã được cấu hình chưa"""
    return os.path.exists(CREDENTIALS_PATH)


async def check_gmail_authorized(user_id: str) -> bool:
    """Kiểm tra đã authorize Gmail chưa (dựa vào BD)"""
    from services.db_service import get_google_credentials
    creds = await get_google_credentials(user_id)
    return bool(creds and creds.get("encrypted_access_token"))


async def send_email(
    user_id: str,
    subject: str,
    body: str,
    recipients: list[str],
) -> dict:
    """
    Gửi email qua Gmail API.

    Args:
        user_id: ID người dùng (để lấy OAuth credentials)
        subject: Tiêu đề email
        body: Nội dung email (plain text)
        recipients: Danh sách email người nhận

    Returns:
        {"success": True, "message_id": "..."} hoặc {"success": False, "error": "..."}
    """
    from email.mime.text import MIMEText
    import base64

    try:
        service = await _get_gmail_service(user_id)

        # Tạo MIME message
        message = MIMEText(body, "plain", "utf-8")
        message["to"] = ", ".join(recipients)
        message["subject"] = subject

        # Encode thành base64url
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")

        # Gửi email
        sent = (
            service.users()
            .messages()
            .send(userId="me", body={"raw": raw})
            .execute()
        )

        msg_id = sent.get("id", "")
        print(f"[EmailTools] ✅ Email sent successfully. ID: {msg_id}")
        return {"success": True, "message_id": msg_id}

    except ValueError as e:
        print(f"[EmailTools] ❌ Auth error: {e}")
        return {"success": False, "error": f"Chưa kết nối Gmail: {e}"}
    except Exception as e:
        print(f"[EmailTools] ❌ Send email error: {e}")
        return {"success": False, "error": str(e)}
