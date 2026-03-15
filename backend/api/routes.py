"""
routes.py - REST API Endpoints
Định nghĩa các endpoint cho frontend gọi
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from agents.graph import get_compiled_graph
from memory.user_context import initialize_user_profile
from langchain_core.messages import HumanMessage
import traceback

router = APIRouter()


# === Request/Response Models ===

class ChatRequest(BaseModel):
    """Request body cho chat endpoint"""
    message: str
    user_id: str = "default_user"


class ChatResponse(BaseModel):
    """Response body cho chat endpoint"""
    response: str
    route: Optional[str] = None
    route_reasoning: Optional[str] = None


class UserProfileRequest(BaseModel):
    """Request body cho user profile initialization"""
    user_id: str
    name: str
    occupation: str = ""
    interests: list[str] = []
    preferred_news_sources: list[str] = []
    work_style: str = ""


# === Chat Endpoint ===

@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Endpoint chính để giao tiếp với AI.
    """
    try:
        graph = get_compiled_graph()

        # Khởi tạo state ban đầu (dùng empty string thay vì None)
        initial_state = {
            "messages": [HumanMessage(content=request.message)],
            "user_id": request.user_id,
            "user_context": "",
            "route": "",
            "route_reasoning": "",
            "tool_results": "",
            "final_response": "",
            "error": "",
        }

        # Chạy graph
        print(f"[API] Invoking graph with message: {request.message[:100]}")
        result = graph.invoke(initial_state)
        print(f"[API] Graph result keys: {list(result.keys())}")

        return ChatResponse(
            response=result.get("final_response", "Xin lỗi, tôi không thể xử lý yêu cầu này.") or "Xin lỗi, tôi không thể xử lý.",
            route=result.get("route") or None,
            route_reasoning=result.get("route_reasoning") or None,
        )

    except Exception as e:
        print(f"[API] Lỗi chat: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Lỗi xử lý: {str(e)}")


# === User Profile Endpoint ===

@router.post("/user/profile")
async def create_user_profile(request: UserProfileRequest):
    """Khởi tạo profile người dùng"""
    try:
        success = initialize_user_profile(
            user_id=request.user_id,
            profile={
                "name": request.name,
                "occupation": request.occupation,
                "interests": request.interests,
                "preferred_news_sources": request.preferred_news_sources,
                "work_style": request.work_style,
            },
        )

        if success:
            return {"status": "ok", "message": f"Đã tạo profile cho {request.name}"}
        else:
            raise HTTPException(status_code=500, detail="Không thể tạo profile")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# === Gmail Status ===

@router.get("/gmail/status")
async def gmail_status():
    """Kiểm tra trạng thái Gmail API"""
    from tools.email_tools import check_gmail_configured, check_gmail_authorized
    return {
        "configured": check_gmail_configured(),
        "authorized": check_gmail_authorized(),
    }


# === Graph Info ===

@router.get("/graph/info")
async def graph_info():
    """Thông tin về cấu trúc graph hiện tại"""
    return {
        "nodes": ["memory_injector", "router", "email_node", "news_node", "general_node"],
        "flow": "START → memory_injector → router → [email|news|general] → END",
        "version": "Phase 3-4 - Email & News Agents",
    }
