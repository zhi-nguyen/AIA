"""
state.py - LangGraph AgentState Definition
Định nghĩa trạng thái chia sẻ giữa các Agent trong graph
"""

from typing import TypedDict, Annotated, Optional
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """
    Trạng thái chia sẻ giữa các Node trong LangGraph.
    Chỉ dùng str thay vì Optional/Literal để tránh lỗi LangGraph.
    """
    messages: Annotated[list, add_messages]
    user_id: str
    user_context: str
    route: str
    route_reasoning: str
    tool_results: str
    final_response: str
    error: str
