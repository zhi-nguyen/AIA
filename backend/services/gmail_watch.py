"""
gmail_watch.py — Gmail Push Notifications via Google Cloud Pub/Sub

Thay thế cơ chế Celery Beat polling (30s) bằng event-driven:
1. register_gmail_watch()  — Gọi Gmail API users.watch() để đăng ký Pub/Sub topic
2. start_pubsub_listener() — Coroutine lắng nghe Pull Subscription, khi có signal → fetch email mới

Flow:
  [Gmail nhận email mới]
       ↓ push notification
  [Google Pub/Sub Topic: gmail-push]
       ↓ pull
  [AIA Backend listener]
       ↓ parse historyId
  [fetch_unread_emails + process_email_intent]
"""

import asyncio
import json
import base64
import traceback
from datetime import datetime

from google.cloud import pubsub_v1
from google.api_core.exceptions import AlreadyExists

from config import get_settings

settings = get_settings()

# Pub/Sub fully-qualified names
_TOPIC_PATH = f"projects/{settings.pubsub_project_id}/topics/{settings.pubsub_topic_id}"
_SUBSCRIPTION_PATH = f"projects/{settings.pubsub_project_id}/subscriptions/{settings.pubsub_subscription_id}"


# ---------------------------------------------------------------------------
# 1. Đăng ký Gmail Watch cho một user
# ---------------------------------------------------------------------------

async def register_gmail_watch(user_id: str) -> dict | None:
    """
    Gọi Gmail API users.watch() để Google push notification vào Pub/Sub topic
    khi hộp thư của user thay đổi.
    Watch có hiệu lực tối đa 7 ngày → cần renew định kỳ.
    """
    try:
        from tools.email_tools import _get_gmail_service

        service = await _get_gmail_service(user_id)
        watch_response = service.users().watch(
            userId="me",
            body={
                "labelIds": ["INBOX"],
                "topicName": _TOPIC_PATH,
                "labelFilterBehavior": "INCLUDE",
            },
        ).execute()

        history_id = watch_response.get("historyId")
        expiration = watch_response.get("expiration")

        print(
            f"[GmailWatch] ✅ Đăng ký watch cho user={user_id[:8]}… "
            f"historyId={history_id} expiration={expiration}"
        )
        return watch_response

    except Exception as e:
        print(f"[GmailWatch] ❌ Lỗi đăng ký watch user={user_id[:8]}…: {e}")
        traceback.print_exc()
        return None


async def register_all_users_watch():
    """
    Đăng ký watch cho TẤT CẢ users đã cấp phép Gmail.
    Gọi khi server khởi động và mỗi 6 ngày để renew.
    """
    from services.db_service import get_all_authorized_users

    users = await get_all_authorized_users()
    print(f"[GmailWatch] Đăng ký watch cho {len(users)} user(s)…")

    for uid in users:
        await register_gmail_watch(uid)
        await asyncio.sleep(0.5)  # Tránh rate limit

    print("[GmailWatch] ✅ Hoàn thành đăng ký watch tất cả users")


# ---------------------------------------------------------------------------
# 2. Xử lý khi nhận được notification từ Pub/Sub
# ---------------------------------------------------------------------------

async def _handle_notification(email_address: str, history_id: str):
    """
    Khi Pub/Sub báo có thay đổi mailbox:
    1. Tìm user_id theo email trong DB
    2. Gọi fetch_unread_emails (Tier 1 DB diff + Tier 2 Regex)
    3. Đẩy qua process_email_intent cho AI phân tích
    """
    from services.db_service import get_user_id_by_email
    from tools.email_tools import fetch_unread_emails, check_gmail_authorized
    from agents.email_agent import process_email_intent

    user_id = await get_user_id_by_email(email_address)
    if not user_id:
        print(f"[GmailWatch] ⚠️ Không tìm thấy user cho email={email_address}")
        return

    if not await check_gmail_authorized(user_id):
        print(f"[GmailWatch] ⚠️ User {user_id[:8]}… chưa cấp phép Gmail")
        return

    print(f"[GmailWatch] 📩 Có email mới cho {email_address} (historyId={history_id})")

    try:
        emails = await fetch_unread_emails(user_id=user_id, limit=10)
        print(f"[GmailWatch] → {len(emails)} email qua bộ lọc")

        for email_data in emails:
            try:
                await process_email_intent(user_id=user_id, email_data=email_data)
            except Exception as email_err:
                print(f"[GmailWatch] Lỗi intent email {email_data.get('id')}: {email_err}")

    except Exception as e:
        print(f"[GmailWatch] Lỗi fetch emails cho {email_address}: {e}")
        traceback.print_exc()


# ---------------------------------------------------------------------------
# 3. Background Listener — Pull messages từ Pub/Sub Subscription
# ---------------------------------------------------------------------------

async def start_pubsub_listener():
    """
    Coroutine chạy vô hạn, pull message từ Pub/Sub subscription.
    Mỗi message chứa { emailAddress, historyId } từ Gmail.

    Chạy trong asyncio event loop của FastAPI (không cần Celery Beat).
    """
    print(f"[GmailWatch] 🎧 Khởi động Pub/Sub listener trên {_SUBSCRIPTION_PATH}")

    # Dùng synchronous subscriber trong thread để không block event loop
    subscriber = pubsub_v1.SubscriberClient()

    # Đảm bảo subscription tồn tại
    try:
        subscriber.create_subscription(
            request={
                "name": _SUBSCRIPTION_PATH,
                "topic": _TOPIC_PATH,
                "ack_deadline_seconds": 30,
            }
        )
        print(f"[GmailWatch] Đã tạo subscription: {_SUBSCRIPTION_PATH}")
    except AlreadyExists:
        print(f"[GmailWatch] Subscription đã tồn tại: {_SUBSCRIPTION_PATH}")
    except Exception as e:
        print(f"[GmailWatch] ⚠️ Không thể kiểm tra subscription: {e}")

    # Pull loop
    while True:
        try:
            # Pull tối đa 10 messages cùng lúc
            response = await asyncio.to_thread(
                subscriber.pull,
                request={
                    "subscription": _SUBSCRIPTION_PATH,
                    "max_messages": 10,
                },
                timeout=30,
            )

            if not response.received_messages:
                # Không có message → đợi rồi pull lại
                await asyncio.sleep(2)
                continue

            ack_ids = []
            for received_message in response.received_messages:
                ack_ids.append(received_message.ack_id)

                try:
                    data = json.loads(received_message.message.data.decode("utf-8"))
                    email_address = data.get("emailAddress", "")
                    history_id = str(data.get("historyId", ""))

                    if email_address:
                        # Xử lý async — không block pull loop
                        asyncio.create_task(
                            _handle_notification(email_address, history_id)
                        )
                except Exception as parse_err:
                    print(f"[GmailWatch] Lỗi parse message: {parse_err}")

            # ACK tất cả messages đã nhận
            if ack_ids:
                await asyncio.to_thread(
                    subscriber.acknowledge,
                    request={
                        "subscription": _SUBSCRIPTION_PATH,
                        "ack_ids": ack_ids,
                    },
                )

        except Exception as e:
            print(f"[GmailWatch] Pull error: {e}")
            await asyncio.sleep(5)  # Backoff trước khi retry


# ---------------------------------------------------------------------------
# 4. Renew Watch — Chạy mỗi 6 ngày để gia hạn (watch hết hạn sau 7 ngày)
# ---------------------------------------------------------------------------

async def _renew_watch_loop():
    """Background loop: gia hạn watch mỗi 6 ngày."""
    while True:
        await asyncio.sleep(6 * 24 * 3600)  # 6 ngày
        print("[GmailWatch] 🔄 Gia hạn watch cho tất cả users…")
        await register_all_users_watch()
