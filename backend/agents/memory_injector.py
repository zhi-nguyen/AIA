"""
memory_injector.py - Memory Injector Node
Kéo thông tin user từ pgvector và inject vào state trước khi xử lý
"""

from agents.state import AgentState
from memory.user_context import retrieve_user_context


def memory_injector_node(state: AgentState) -> dict:
    """
    Node Memory Injector trong LangGraph.
    
    Chạy TRƯỚC Router để:
    1. Lấy user context từ pgvector (profile, sở thích, lịch sử)
    2. Inject vào state để các Agent khác có thể sử dụng
    
    Phiên tạm (is_temporary=True): Bỏ qua hoàn toàn, trả về context rỗng.
    """
    user_id = state.get("user_id", "default_user")
    is_temporary = state.get("is_temporary", False)

    if is_temporary:
        print(f"[MemoryInjector] Phiên tạm — bỏ qua user context cho {user_id}")
        return {"user_context": ""}

    try:
        user_context = retrieve_user_context(user_id)
        print(f"[MemoryInjector] Đã lấy context cho user: {user_id}")
        return {"user_context": user_context}
    except Exception as e:
        print(f"[MemoryInjector] Lỗi khi lấy context: {e}")
        return {"user_context": "Chưa có thông tin người dùng."}
