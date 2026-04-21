"""
websocket.py - WebSocket Handler
Quản lý kết nối WebSocket cho Web Client và Agent Client.
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict, Any

router = APIRouter()

class ConnectionManager:
    def __init__(self) -> None:
        self.active_agents: Dict[str, WebSocket] = {}
        self.active_web_clients: Dict[str, WebSocket] = {}
        self.agent_tokens: Dict[str, str] = {}

    async def connect_agent(self, websocket: WebSocket, user_id: str, token: str) -> bool:
        expected_token = self.agent_tokens.get(user_id)
        if not expected_token or token != expected_token:
            await websocket.close(code=1008, reason="Invalid or missing token")
            return False
            
        await websocket.accept()
        self.active_agents[user_id] = websocket
        print(f"[WebSocket] Agent connected for user {user_id}")
        return True

    def disconnect_agent(self, user_id: str) -> None:
        if user_id in self.active_agents:
            del self.active_agents[user_id]
            print(f"[WebSocket] Agent disconnected for user {user_id}")
            
    async def connect_web(self, websocket: WebSocket, user_id: str) -> None:
        await websocket.accept()
        self.active_web_clients[user_id] = websocket
        print(f"[WebSocket] Web client connected for user {user_id}")
        
    def disconnect_web(self, user_id: str) -> None:
        if user_id in self.active_web_clients:
            del self.active_web_clients[user_id]
            print(f"[WebSocket] Web client disconnected for user {user_id}")
            
    async def send_to_agent(self, user_id: str, message: Dict[str, Any]) -> bool:
        if user_id in self.active_agents:
            await self.active_agents[user_id].send_json(message)
            return True
        return False

    async def send_to_web(self, user_id: str, message: Dict[str, Any]) -> bool:
        if user_id in self.active_web_clients:
            await self.active_web_clients[user_id].send_json(message)
            return True
        return False

manager = ConnectionManager()

@router.websocket("/ws/agent/{user_id}")
async def websocket_agent_endpoint(websocket: WebSocket, user_id: str, token: str = "") -> None:
    success = await manager.connect_agent(websocket, user_id, token)
    if not success:
        return
    try:
        while True:
            data = await websocket.receive_text()
            # Xử lý thông điệp từ Agent nếu cần
            print(f"[Agent -> Backend: {user_id}] {data}")
    except WebSocketDisconnect:
        manager.disconnect_agent(user_id)
        
@router.websocket("/ws/web/{user_id}")
async def websocket_web_endpoint(websocket: WebSocket, user_id: str) -> None:
    await manager.connect_web(websocket, user_id)
    
    # Kích hoạt Background Task xử lý Offline Queue
    from tasks import process_offline_queue
    process_offline_queue.delay(user_id)

    try:
        while True:
            data = await websocket.receive_text()
            # Xử lý thông điệp từ Web Client nếu cần
            print(f"[Web -> Backend: {user_id}] {data}")
    except WebSocketDisconnect:
        manager.disconnect_web(user_id)
