"""
local_tools.py - Local Environment Tools
Chứa các công cụ cho phép AI điều khiển môi trường máy tính cục bộ của người dùng (tạo file Word, Excel, ...).

NOTE: Các hàm này được gọi từ Celery Worker (process riêng), KHÔNG có quyền truy cập
WebSocket ConnectionManager trực tiếp. Vì vậy giao tiếp qua Redis Pub/Sub.
"""

from typing import Dict, Any, List
import json
import redis
from celery_app import redis_url


def _publish_to_agent(user_id: str, payload: Dict[str, Any]) -> bool:
    """
    Publish lệnh tới Agent thông qua Redis Pub/Sub.
    FastAPI listener sẽ nhận và forward tới Agent qua WebSocket.
    """
    try:
        r = redis.from_url(redis_url)
        message = {
            "user_id": user_id,
            "type": "agent_command",  # Đánh dấu để FastAPI chỉ gửi cho Agent, không gửi cho Web
            **payload,
        }
        r.publish("aia_ws_messages", json.dumps(message))
        print(f"[LocalTools] Published agent command via Redis: action={payload.get('action')}")
        return True
    except Exception as e:
        print(f"[LocalTools] Redis publish error: {e}")
        return False


async def trigger_local_word(user_id: str, template: str, data: Dict[str, Any]) -> str:
    """
    Sử dụng công cụ này để yêu cầu máy tính cục bộ của người dùng
    tạo một file Word với dữ liệu đã điền sẵn.
    """
    payload = {
        "action": "create_word",
        "data": {
            "template_name": template,
            "data": data
        }
    }
    success = _publish_to_agent(user_id, payload)
    if success:
        return "Successfully dispatched Word generation command to the client machine."
    return "Failed to dispatch command. Redis might be unavailable."

async def trigger_local_excel(user_id: str, data: List[Dict[str, Any]]) -> str:
    """
    Sử dụng công cụ này để yêu cầu máy tính cục bộ của người dùng
    tạo một báo cáo Excel với dữ liệu được cung cấp.
    """
    payload = {
        "action": "create_excel",
        "data": data
    }
    success = _publish_to_agent(user_id, payload)
    if success:
        return "Successfully dispatched Excel generation command to the client machine."
    return "Failed to dispatch command. Redis might be unavailable."
