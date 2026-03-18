# backend/agents/news_agent.py
"""
news_agent.py - News Agent Node
Xử lý các yêu cầu liên quan đến tin tức.
Hỗ trợ intent recognition: tách câu hỏi đa chủ đề thành nhiều search queries riêng biệt.
"""

import json
import re
from datetime import datetime
from typing import Optional

from agents.state import AgentState
from llm.gemini_client import get_gemini_client
from llm.prompts import NEWS_INTENT_PROMPT
from tools.news_tools import fetch_news, summarize_news
from langchain_core.messages import HumanMessage


def _extract_news_queries(user_message: str) -> list[str]:
    """
    Dùng Gemini Flash để phân tích intent và trích xuất
    các search queries riêng biệt từ câu hỏi người dùng.

    VD: "Giá vàng thế nào? Tin công nghệ mới? Chiến sự Trung Đông?"
     → ["Giá vàng hôm nay", "Tin tức công nghệ mới", "Tin tức chiến sự Trung Đông"]

    Fallback: trả về [user_message] nếu Gemini parse thất bại.
    """
    client = get_gemini_client()
    prompt = NEWS_INTENT_PROMPT.format(user_message=user_message)

    try:
        response = client.generate_flash(prompt)
        print(f"[NewsAgent] Intent raw response: {response[:300]}")

        # Parse JSON
        clean = response.strip()
        if "```" in clean:
            match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", clean, re.DOTALL)
            if match:
                clean = match.group(1).strip()

        result = json.loads(clean)
        queries = result.get("queries", [])

        if isinstance(queries, list) and len(queries) > 0:
            # Validate: chỉ giữ string, bỏ rỗng
            valid_queries = [q.strip() for q in queries if isinstance(q, str) and q.strip()]
            if valid_queries:
                print(f"[NewsAgent] Extracted {len(valid_queries)} queries: {valid_queries}")
                return valid_queries

        # queries rỗng = câu hỏi chung chung → trả rỗng để fallback RSS
        print("[NewsAgent] No specific queries extracted (generic question)")
        return []

    except (json.JSONDecodeError, KeyError) as e:
        print(f"[NewsAgent] JSON parse failed: {e}, fallback to raw message")
        return [user_message]
    except Exception as e:
        print(f"[NewsAgent] Intent extraction error: {e}, fallback to raw message")
        return [user_message]


def _deduplicate_articles(articles: list[dict]) -> list[dict]:
    """Loại bỏ bài viết trùng lặp dựa trên URL."""
    seen_urls: set[str] = set()
    unique: list[dict] = []
    for article in articles:
        url = article.get("url", "")
        if url and url not in seen_urls:
            seen_urls.add(url)
            unique.append(article)
        elif not url:
            unique.append(article)
    return unique


def news_node(state: AgentState) -> dict:
    """
    Node News Agent trong LangGraph.

    Flow:
    1. Trích xuất intent → tách thành nhiều search queries
    2. Fetch tin tức cho TỪNG query riêng biệt
    3. Gộp + loại trùng kết quả
    4. Tóm tắt bằng Gemini Flash
    5. Trả về response dạng formatted markdown
    """
    # Lấy tin nhắn cuối
    last_message = ""
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage) or (hasattr(msg, "type") and msg.type == "human"):
            last_message = msg.content if hasattr(msg, "content") else str(msg)
            break

    try:
        # === Bước 1: Trích xuất search queries từ intent ===
        queries = _extract_news_queries(last_message)

        # === Bước 2: Fetch tin tức cho từng query ===
        all_articles: list[dict] = []

        if queries:
            # Có queries cụ thể → search riêng từng query
            per_query_limit = max(8 // len(queries), 3)
            for query in queries:
                print(f"[NewsAgent] Fetching news for query: '{query}'")
                articles = fetch_news(query=query, limit=per_query_limit)
                all_articles.extend(articles)
        else:
            # Câu hỏi chung chung → fetch RSS mặc định
            print("[NewsAgent] Generic question, fetching default RSS feeds")
            all_articles = fetch_news(query=last_message, limit=8)

        # === Bước 3: Loại trùng ===
        all_articles = _deduplicate_articles(all_articles)
        print(f"[NewsAgent] Total unique articles: {len(all_articles)}")

        if not all_articles:
            return {
                "final_response": "Không tìm thấy tin tức nào phù hợp. Hãy thử từ khóa khác nhé!",
                "tool_results": json.dumps({"status": "no_results"}),
                "search_queries": json.dumps(queries, ensure_ascii=False),
            }

        # === Bước 4: Tóm tắt tin tức ===
        today_str = datetime.now().strftime("%d/%m/%Y")
        user_context = state.get("user_context", "")
        context_with_date = f"Hôm nay là ngày {today_str}.\n{user_context}"

        summary = summarize_news(
            all_articles,
            query=last_message,
            user_preferences=context_with_date,
        )
        news_list = summary.get("news", [])

        # === Bước 5: Format response ===
        response_parts = [f"**Tin tức liên quan ({len(news_list)} bài):**\n"]

        for i, news_item in enumerate(news_list, 1):
            summary_text = news_item.get("summary", "").strip()
            summary_line = (
                f"Tóm tắt: {summary_text}  \n"
                if summary_text
                and summary_text.lower()
                not in [
                    "không có thông tin",
                    "mời bạn bấm vào link để xem chi tiết bài báo này.",
                ]
                else ""
            )

            response_parts.append(
                f"**{i}. {news_item.get('title', 'Không có tiêu đề')}**  \n"
                f"Nguồn: {news_item.get('source', 'Không rõ nguồn')}  \n"
                f"{summary_line}"
                f"[Đọc thêm]({news_item.get('url', '')})  \n\n"
            )

        # Nếu Gemini không parse được JSON, dùng raw articles
        if not news_list and all_articles:
            news_list = [
                {
                    "title": a["title"],
                    "source": a["source"],
                    "summary": a["summary"][:200] if a.get("summary") else "",
                    "url": a["url"],
                }
                for a in all_articles[:5]
            ]

        return {
            "final_response": "\n".join(response_parts),
            "tool_results": json.dumps(summary, ensure_ascii=False),
            "search_queries": json.dumps(queries, ensure_ascii=False),
        }

    except Exception as e:
        print(f"[NewsAgent] Lỗi: {e}")
        return {
            "final_response": f"Xin lỗi, tôi gặp lỗi khi tìm tin tức: {str(e)}",
            "tool_results": json.dumps({"error": str(e)}),
            "search_queries": json.dumps([], ensure_ascii=False),
        }
