"""
news_agent.py - News Agent Node
Xử lý các yêu cầu liên quan đến tin tức
"""

import json
from agents.state import AgentState
from llm.gemini_client import get_gemini_client
from tools.news_tools import fetch_news, summarize_news
from langchain_core.messages import HumanMessage


def news_node(state: AgentState) -> dict:
    """
    Node News Agent trong LangGraph.
    
    Flow:
    1. Phân tích yêu cầu người dùng
    2. Fetch tin tức từ RSS feeds
    3. Tóm tắt bằng Gemini Flash
    4. Trả về response dạng cards
    """
    # Lấy tin nhắn cuối
    last_message = ""
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage) or (hasattr(msg, "type") and msg.type == "human"):
            last_message = msg.content if hasattr(msg, "content") else str(msg)
            break

    try:
        # === Fetch tin tức ===
        articles = fetch_news(query=last_message, limit=8)

        if not articles:
            return {
                "final_response": "Không tìm thấy tin tức nào phù hợp. Hãy thử từ khóa khác nhé!",
                "tool_results": json.dumps({"status": "no_results"}),
            }

        # === Tóm tắt tin tức ===
        from datetime import datetime
        today_str = datetime.now().strftime("%d/%m/%Y")
        
        user_context = state.get("user_context", "")
        context_with_date = f"Hôm nay là ngày {today_str}.\n{user_context}"
        
        summary = summarize_news(articles, query=last_message, user_preferences=context_with_date)
        news_list = summary.get("news", [])

        # === Format response đẹp ===
        response_parts = [f"**Tin tức liên quan ({len(news_list)} bài):**\n"]

        for i, news_item in enumerate(news_list, 1):
            summary_text = news_item.get('summary', '').strip()
            summary_line = f"Tóm tắt: {summary_text}  \n" if summary_text and summary_text.lower() not in ["không có thông tin", "mời bạn bấm vào link để xem chi tiết bài báo này."] else ""
            
            response_parts.append(
                f"**{i}. {news_item.get('title', 'Không có tiêu đề')}**  \n"
                f"Nguồn: {news_item.get('source', 'Không rõ nguồn')}  \n"
                f"{summary_line}"
                f"[Đọc thêm]({news_item.get('url', '')})  \n\n"
            )

        # Nếu Gemini không parse được JSON, dùng raw articles
        if not news_list and articles:
            news_list = [
                {
                    "title": a["title"],
                    "source": a["source"],
                    "summary": a["summary"][:200] if a.get("summary") else "",
                    "url": a["url"],
                }
                for a in articles[:5]
            ]

        return {
            "final_response": "\n".join(response_parts),
            "tool_results": json.dumps(summary, ensure_ascii=False),
        }

    except Exception as e:
        print(f"[NewsAgent] Lỗi: {e}")
        return {
            "final_response": f"Xin lỗi, tôi gặp lỗi khi tìm tin tức: {str(e)}",
            "tool_results": json.dumps({"error": str(e)}),
        }
