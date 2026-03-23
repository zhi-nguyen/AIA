"""
graph.py - LangGraph Graph Wiring
Kết nối tất cả các Agent nodes thành một workflow hoàn chỉnh
"""

from langgraph.graph import StateGraph, START, END
from agents.state import AgentState
from agents.memory_injector import memory_injector_node
from agents.router import router_node
from agents.email_agent import email_node
from agents.news_agent import news_node
from agents.document_agent import document_node
from llm.gemini_client import get_gemini_client
from llm.prompts import GENERAL_CHAT_PROMPT
from langchain_core.messages import HumanMessage

import json
from agents.router import _extract_json
from tools.local_tools import trigger_local_word, trigger_local_excel

async def general_chat_node(state: AgentState) -> dict:
    """
    Node General Chat - Trả lời các câu hỏi chung và chạy lệnh công cụ cục bộ.
    Dùng Gemini Pro cho chất lượng trả lời tốt.
    """
    client = get_gemini_client()

    # Lấy tin nhắn cuối
    last_message = ""
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage) or (hasattr(msg, "type") and msg.type == "human"):
            last_message = msg.content if hasattr(msg, "content") else str(msg)
            break

    # Lấy user id để gọi công cụ
    user_id = state.get("user_id", "default_user")

    # Tạo chat history string
    chat_history = ""
    for msg in state["messages"][-10:]:  # Giữ 10 tin nhắn gần nhất
        role = "User" if (isinstance(msg, HumanMessage) or (hasattr(msg, "type") and msg.type == "human")) else "AI"
        content = msg.content if hasattr(msg, "content") else str(msg)
        chat_history += f"{role}: {content}\n"

    system_prompt = GENERAL_CHAT_PROMPT.format(
        user_context=state.get("user_context", "Chưa có thông tin"),
        chat_history=chat_history,
    )

    response = client.generate_pro(last_message, system_instruction=system_prompt)
    
    # Kiểm tra xem AI có yêu cầu chạy tool cục bộ không
    extracted_json = _extract_json(response)
    if extracted_json and "action" in extracted_json:
        action = extracted_json["action"]
        data = extracted_json.get("data", {})
        
        try:
            if action == "trigger_local_word":
                template = data.get("template", "contract")
                word_data = data.get("data", {})
                result = await trigger_local_word(user_id, template, word_data)
                return {"final_response": "Đã gửi yêu cầu cấp phát Word script tới máy của bạn. Hãy xác nhận trên máy tính.", "tool_results": result}
            
            elif action == "trigger_local_excel":
                result = await trigger_local_excel(user_id, data)
                return {"final_response": "Đã gửi yêu cầu xuất file Excel. Hãy kiểm tra máy tính của bạn.", "tool_results": result}
        except Exception as e:
            return {"final_response": f"Có lỗi xảy ra khi thực thi công cụ cục bộ: {str(e)}"}

    return {"final_response": response}


def route_decision(state: AgentState) -> str:
    """
    Conditional edge function - Quyết định route dựa trên kết quả Router.
    """
    route = state.get("route", "general")
    if route == "email":
        return "email_node"
    elif route == "news":
        return "news_node"
    elif route == "document":
        return "document_node"
    else:
        return "general_node"


def build_graph() -> StateGraph:
    """
    Xây dựng LangGraph StateGraph hoàn chỉnh.
    
    Flow:
    START → memory_injector → router → [email_node | news_node | general_node] → END
    """
    # === Khởi tạo Graph ===
    graph = StateGraph(AgentState)

    # === Thêm các Nodes ===
    graph.add_node("memory_injector", memory_injector_node)
    graph.add_node("router", router_node)
    graph.add_node("email_node", email_node)
    graph.add_node("news_node", news_node)
    graph.add_node("document_node", document_node)
    graph.add_node("general_node", general_chat_node)

    # === Kết nối Edges ===
    # START → Memory Injector → Router
    graph.add_edge(START, "memory_injector")
    graph.add_edge("memory_injector", "router")

    # Router → Conditional routing
    graph.add_conditional_edges(
        "router",
        route_decision,
        {
            "email_node": "email_node",
            "news_node": "news_node",
            "document_node": "document_node",
            "general_node": "general_node",
        },
    )

    # Tất cả Agent nodes → END
    graph.add_edge("email_node", END)
    graph.add_edge("news_node", END)
    graph.add_edge("document_node", END)
    graph.add_edge("general_node", END)

    return graph


# === Compile graph (singleton) ===
_compiled_graph = None


def get_compiled_graph():
    """Lấy compiled graph (singleton pattern)"""
    global _compiled_graph
    if _compiled_graph is None:
        graph = build_graph()
        _compiled_graph = graph.compile()
    return _compiled_graph
