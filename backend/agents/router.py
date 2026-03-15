"""
router.py - Supervisor/Router Agent
Dùng Gemini Pro để phân tích intent và chọn Agent phù hợp
"""

import json
import re
from agents.state import AgentState
from llm.gemini_client import get_gemini_client
from llm.prompts import ROUTER_SYSTEM_PROMPT
from langchain_core.messages import HumanMessage


# Từ khóa đơn giản để fallback khi Gemini không trả JSON đúng
EMAIL_KEYWORDS = ["email", "mail", "hộp thư", "inbox", "thư", "gmail", "gửi mail", "đọc mail"]
NEWS_KEYWORDS = ["tin tức", "tin", "news", "báo", "cập nhật", "thời sự", "headline"]


def _classify_by_keywords(text: str) -> str:
    """Phân loại đơn giản bằng keyword khi Gemini parse fail"""
    lower = text.lower()
    for kw in EMAIL_KEYWORDS:
        if kw in lower:
            return "email"
    for kw in NEWS_KEYWORDS:
        if kw in lower:
            return "news"
    return "general"


def _extract_json(text: str) -> dict:
    """Trích xuất JSON từ response Gemini (xử lý markdown, text thừa, etc.)"""
    clean = text.strip()

    # Bỏ markdown code block nếu có
    if "```" in clean:
        match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", clean, re.DOTALL)
        if match:
            clean = match.group(1).strip()

    # Thử parse trực tiếp
    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        pass

    # Tìm JSON object đầu tiên trong text
    match = re.search(r"\{[^}]+\}", clean)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    return {}


def router_node(state: AgentState) -> dict:
    """
    Node Router/Supervisor trong LangGraph.
    
    Phân tích câu lệnh cuối cùng của user và quyết định route:
    - "email": Chuyển đến EmailAgent
    - "news": Chuyển đến NewsAgent  
    - "general": Trả lời trực tiếp
    """
    client = get_gemini_client()

    # Lấy tin nhắn cuối cùng từ user
    last_message = ""
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage) or (hasattr(msg, "type") and msg.type == "human"):
            last_message = msg.content if hasattr(msg, "content") else str(msg)
            break

    if not last_message:
        return {"route": "general", "route_reasoning": "Không tìm thấy tin nhắn"}

    # Chuẩn bị prompt với user context
    system_prompt = ROUTER_SYSTEM_PROMPT.format(
        user_context=state.get("user_context", "Chưa có thông tin")
    )

    prompt = f"Phân tích yêu cầu sau và quyết định route:\n\n\"{last_message}\""

    try:
        response = client.generate_pro(prompt, system_instruction=system_prompt)
        print(f"[Router] Raw response: {response[:200]}")

        # Parse JSON từ response
        result = _extract_json(response)

        if result and "route" in result:
            route = result["route"]
            reasoning = result.get("reasoning", "")

            # Validate route
            if route not in ("email", "news", "general"):
                route = "general"

            print(f"[Router] Route: {route} | Reason: {reasoning}")
            return {"route": route, "route_reasoning": reasoning}
        else:
            # Fallback: classify bằng keyword
            route = _classify_by_keywords(last_message)
            print(f"[Router] JSON parse failed, fallback keyword → {route}")
            return {"route": route, "route_reasoning": "Fallback: keyword classification"}

    except Exception as e:
        print(f"[Router] Lỗi: {e}")
        route = _classify_by_keywords(last_message)
        return {"route": route, "route_reasoning": f"Fallback do lỗi: {str(e)}"}
