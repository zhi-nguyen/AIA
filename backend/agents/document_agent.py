"""
document_agent.py - Document Q&A Agent
Trả lời câu hỏi dựa trên nội dung tài liệu đã upload
"""

from agents.state import AgentState
from llm.gemini_client import get_gemini_client
from llm.prompts import DOCUMENT_AGENT_PROMPT
from langchain_core.messages import HumanMessage


def document_node(state: AgentState) -> dict:
    """
    Node Document Agent trong LangGraph.
    Sử dụng document_context để trả lời câu hỏi user.
    """
    client = get_gemini_client()

    # Lấy tin nhắn cuối
    last_message = ""
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage) or (hasattr(msg, "type") and msg.type == "human"):
            last_message = msg.content if hasattr(msg, "content") else str(msg)
            break

    document_context = state.get("document_context", "")

    if not document_context:
        return {"final_response": "Chưa có tài liệu nào được tải lên. Hãy đính kèm file trước nhé!"}

    # Tạo prompt
    system_prompt = DOCUMENT_AGENT_PROMPT.format(
        user_context=state.get("user_context", "Chưa có thông tin"),
        document_context=document_context,
    )

    try:
        response = client.generate_pro(last_message, system_instruction=system_prompt)
        return {"final_response": response}
    except Exception as e:
        print(f"[DocumentAgent] Lỗi: {e}")
        return {"final_response": f"Xin lỗi, tôi gặp lỗi khi phân tích tài liệu: {str(e)}"}
