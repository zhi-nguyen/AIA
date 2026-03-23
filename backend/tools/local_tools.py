"""
local_tools.py - Local Environment Tools
Chứa các công cụ cho phép AI điều khiển môi trường máy tính cục bộ của người dùng (tạo file Word, Excel, ...).
"""

from typing import Dict, Any, List
from api.websocket import manager

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
    success = await manager.send_to_agent(user_id, payload)
    if success:
        return "Successfully dispatched Word generation command to the client machine."
    return "Failed to dispatch command. Agent might be offline."

async def trigger_local_excel(user_id: str, data: List[Dict[str, Any]]) -> str:
    """
    Sử dụng công cụ này để yêu cầu máy tính cục bộ của người dùng
    tạo một báo cáo Excel với dữ liệu được cung cấp.
    """
    payload = {
        "action": "create_excel",
        "data": data
    }
    success = await manager.send_to_agent(user_id, payload)
    if success:
        return "Successfully dispatched Excel generation command to the client machine."
    return "Failed to dispatch command. Agent might be offline."
