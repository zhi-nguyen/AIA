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

# Gmail API scopes - chỉ đọc email
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

# Đường dẫn file credentials và token
CREDENTIALS_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "credentials.json")
TOKEN_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "token.json")


def _get_gmail_service():
    """
    Khởi tạo Gmail API service với OAuth2.
    Tự động refresh token nếu hết hạn.
    """
    creds = None

    # Load token đã lưu
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)

    # Nếu chưa có token hoặc token hết hạn
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDENTIALS_PATH):
                raise FileNotFoundError(
                    f"Không tìm thấy {CREDENTIALS_PATH}. "
                    "Hãy tải credentials.json từ Google Cloud Console "
                    "(APIs & Services > Credentials > OAuth 2.0 Client IDs) "
                    "và đặt vào thư mục backend/"
                )
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
            creds = flow.run_local_server(port=8090)

        # Lưu token cho lần sau
        with open(TOKEN_PATH, "w") as token_file:
            token_file.write(creds.to_json())

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


def fetch_unread_emails(limit: int = 5) -> list[dict]:
    """
    Fetch email chưa đọc từ Gmail.
    
    Args:
        limit: Số lượng email tối đa (default: 5)
        
    Returns:
        List[dict] với format:
        [{"id": "...", "subject": "...", "from": "...", "date": "...", "snippet": "...", "body": "..."}]
    """
    try:
        service = _get_gmail_service()

        # Query email chưa đọc
        results = service.users().messages().list(
            userId="me",
            q="is:unread",
            maxResults=limit,
        ).execute()

        messages = results.get("messages", [])
        if not messages:
            return []

        emails = []
        for msg_ref in messages:
            msg = service.users().messages().get(
                userId="me",
                id=msg_ref["id"],
                format="full",
            ).execute()

            headers = msg.get("payload", {}).get("headers", [])
            body = _decode_email_body(msg.get("payload", {}))

            emails.append({
                "id": msg["id"],
                "subject": _get_header(headers, "Subject"),
                "from": _get_header(headers, "From"),
                "date": _get_header(headers, "Date"),
                "snippet": msg.get("snippet", ""),
                "body": body,
            })

        print(f"[EmailTools] Fetched {len(emails)} unread emails")
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


def check_gmail_authorized() -> bool:
    """Kiểm tra đã authorize Gmail chưa"""
    return os.path.exists(TOKEN_PATH)
