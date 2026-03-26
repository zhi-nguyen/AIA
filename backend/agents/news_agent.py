# backend/agents/news_agent.py
"""
news_agent.py - News Agent Node
Xử lý các yêu cầu liên quan đến tin tức.
Hỗ trợ intent recognition: tách câu hỏi đa chủ đề thành nhiều search queries.
Output: 1 đoạn văn tổng hợp + danh sách nguồn tin bên dưới.
+ Phase 7: Proactive Recommendation — generate_proposal_for_user()
"""

import json
import re
from datetime import datetime
from typing import Optional

from agents.state import AgentState
from llm.gemini_client import get_gemini_client
from llm.prompts import NEWS_INTENT_PROMPT, PROPOSAL_SYSTEM_PROMPT
from tools.news_tools import fetch_news, summarize_news, search_vertex_store, parse_gemini_json
from memory.user_context import get_user_profile
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
            valid_queries = [q.strip() for q in queries if isinstance(q, str) and q.strip()]
            if valid_queries:
                print(f"[NewsAgent] Extracted {len(valid_queries)} queries: {valid_queries}")
                return valid_queries

        print("[NewsAgent] No specific queries extracted (generic question)")
        return []

    except (json.JSONDecodeError, KeyError) as e:
        print(f"[NewsAgent] JSON parse failed: {e}, fallback to generic RSS")
        return []
    except Exception as e:
        print(f"[NewsAgent] Intent extraction error: {e}, fallback to generic RSS")
        return []


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
    2. Fetch 1-2 bài viết cho TỪNG query
    3. Gộp + loại trùng kết quả
    4. Tổng hợp thành 1 đoạn văn bản bằng Gemini Flash
    5. Trả về: đoạn tổng hợp + danh sách nguồn tin
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

        # === Bước 2: Fetch tin tức — 1-2 bài / query ===
        all_articles: list[dict] = []
        ARTICLES_PER_QUERY = 2

        if queries:
            for query in queries:
                print(f"[NewsAgent] Fetching news for query: '{query}'")
                articles = fetch_news(query=query, limit=ARTICLES_PER_QUERY, is_extracted_query=True)
                all_articles.extend(articles)
        else:
            # Câu hỏi chung chung → lấy tổng cộng 3-5 bài từ RSS
            print("[NewsAgent] Generic question, fetching default RSS feeds")
            all_articles = fetch_news(query=last_message, limit=5, is_extracted_query=False)

        # === Bước 3: Loại trùng ===
        all_articles = _deduplicate_articles(all_articles)
        print(f"[NewsAgent] Total unique articles: {len(all_articles)}")

        if not all_articles:
            return {
                "final_response": "Không tìm thấy tin tức nào phù hợp. Hãy thử từ khóa khác nhé!",
                "tool_results": json.dumps({"status": "no_results"}),
                "search_queries": json.dumps(queries, ensure_ascii=False),
            }

        # === Bước 4: Tổng hợp thành 1 đoạn văn ===
        today_str = datetime.now().strftime("%d/%m/%Y")
        user_context = state.get("user_context", "")
        context_with_date = f"Hôm nay là ngày {today_str}.\n{user_context}"

        summary_result = summarize_news(
            all_articles,
            query=last_message,
            user_preferences=context_with_date,
        )

        # === Bước 5: Format response ===
        response = _format_synthesized_response(summary_result, all_articles)

        return {
            "final_response": response,
            "tool_results": json.dumps(summary_result, ensure_ascii=False),
            "search_queries": json.dumps(queries, ensure_ascii=False),
        }

    except Exception as e:
        print(f"[NewsAgent] Lỗi: {e}")
        return {
            "final_response": f"Xin lỗi, tôi gặp lỗi khi tìm tin tức: {str(e)}",
            "tool_results": json.dumps({"error": str(e)}),
            "search_queries": json.dumps([], ensure_ascii=False),
        }


def _format_synthesized_response(
    summary_result: dict, fallback_articles: list[dict]
) -> str:
    """
    Format response: đoạn văn tổng hợp + danh sách nguồn tin bên dưới.

    Gemini trả về JSON:
      {"summary": "Đoạn văn...", "sources": [{"title": ..., "source": ..., "url": ...}]}

    Nếu Gemini trả format cũ ({"news": [...]}) hoặc parse fail → fallback.
    """
    # --- Trường hợp 1: Format mới (summary + sources) hoặc Fallback (raw_summary) ---
    paragraph = (
        summary_result.get("summary", "") 
        or summary_result.get("response", "") 
        or summary_result.get("raw_summary", "")
    )
    sources = summary_result.get("sources", []) or summary_result.get("source", [])

    # --- Trường hợp 2: Fallback từ format cũ (news array) ---
    if not paragraph and "news" in summary_result:
        news_list = summary_result["news"]
        if news_list:
            # Ghép summary của từng bài thành 1 đoạn
            parts = [item.get("summary", "") for item in news_list if item.get("summary")]
            paragraph = " ".join(parts) if parts else ""
            sources = [
                {"title": item.get("title", ""), "source": item.get("source", ""), "url": item.get("url", "")}
                for item in news_list
            ]

    # --- Trường hợp 3: Không có gì → dùng raw articles ---
    if not paragraph and fallback_articles:
        titles = [a["title"] for a in fallback_articles[:5]]
        paragraph = "Tin tức nổi bật: " + "; ".join(titles) + "."
        sources = [
            {"title": a["title"], "source": a["source"], "url": a["url"]}
            for a in fallback_articles[:5]
        ]

    # === Build final markdown ===
    response_parts: list[str] = []

    # Đoạn văn tổng hợp
    if paragraph:
        response_parts.append(paragraph)
        response_parts.append("")  # blank line

    # Danh sách nguồn tin
    if sources:
        response_parts.append("---")
        response_parts.append("**Nguồn tin:**")
        for i, src in enumerate(sources, 1):
            title = src.get("title", "Không có tiêu đề")
            source_name = src.get("source", "")
            url = src.get("url", "")
            source_tag = f" — *{source_name}*" if source_name else ""
            if url:
                response_parts.append(f"{i}. [{title}]({url}){source_tag}")
            else:
                response_parts.append(f"{i}. {title}{source_tag}")

    return "\n".join(response_parts)


# ============================================================
# === Phase 7: Proactive Recommendation — Proposal Generator ===
# ============================================================

def generate_proposal_for_user(user_id: str) -> Optional[dict]:
    """
    Tạo đề xuất hành động (Action Proposal) dựa trên:
    1. Profile người dùng (vai trò, sở thích)
    2. Tin tức liên quan từ Vertex AI Search
    3. Gemini tổng hợp thành email proposal

    Args:
        user_id: ID người dùng

    Returns:
        Dict proposal hoặc None nếu không có đề xuất
    """
    # === Bước 1: Lấy profile người dùng ===
    profile = get_user_profile(user_id)
    if not profile:
        print(f"[Proposal] ⚠️ No profile found for user: {user_id}")
        return None

    user_name = profile.get("name", "Người dùng")
    user_role = profile.get("occupation", "Cán bộ bệnh viện")
    interests = profile.get("interests", [])
    news_sources = profile.get("preferred_news_sources", [])

    print(f"[Proposal] 👤 User: {user_name}, Role: {user_role}, Interests: {interests}")

    # === Bước 2: Tìm tin tức liên quan từ Vertex Search ===
    search_queries = interests + news_sources
    if not search_queries:
        search_queries = ["tin tức công nghệ kinh tế mới nhất"]

    all_news: list[dict] = []
    for query in search_queries:
        results = search_vertex_store(query=query, top_k=5)
        all_news.extend(results)

    if not all_news:
        print(f"[Proposal] ⚠️ No relevant news found in Vertex Search")
        return None

    # Loại trùng theo ID
    seen_ids: set[str] = set()
    unique_news: list[dict] = []
    for news in all_news:
        nid = news.get("id", "")
        if nid and nid not in seen_ids:
            seen_ids.add(nid)
            unique_news.append(news)
        elif not nid:
            unique_news.append(news)
    unique_news = unique_news[:15]  # Giới hạn 15 tin để AI tự xử lý lọc

    print(f"[Proposal] 📰 Found {len(unique_news)} unique news items")

    # === Bước 3: Format news context cho prompt ===
    news_context_parts: list[str] = []
    for i, news in enumerate(unique_news, 1):
        meta = news.get("metadata", {})
        tag = meta.get("tag", "")
        source = meta.get("source", "")
        news_context_parts.append(
            f"--- Tin {i} ---\n"
            f"Tiêu đề: {news.get('title', '')}\n"
            f"Nội dung: {news.get('content', '')[:500]}\n"
            f"Chủ đề: {tag}\n"
            f"Nguồn: {source}"
        )
    news_context = "\n\n".join(news_context_parts)

    # === Bước 4: Gọi Gemini để tạo proposal ===
    client = get_gemini_client()
    prompt = PROPOSAL_SYSTEM_PROMPT.format(
        user_name=user_name,
        user_role=user_role,
        user_interests=", ".join(interests) if interests else "Chung",
        news_context=news_context,
    )

    try:
        response = client.generate_flash(prompt)
        print(f"[Proposal] 🤖 Gemini response length: {len(response)}")

        # Parse JSON
        proposals = parse_gemini_json(response)
        if not proposals:
            print(f"[Proposal] ⚠️ Failed to parse proposal JSON")
            return None

        proposal = proposals[0]

        # Nếu Gemini trả no_action → bỏ qua
        if proposal.get("type") == "no_action":
            print(f"[Proposal] ℹ️ No action needed: {proposal.get('reason', '')}")
            return None

        print(f"[Proposal] ✅ Generated proposal: {proposal.get('title', '')[:60]}")
        return proposal

    except Exception as e:
        print(f"[Proposal] ❌ Error generating proposal: {e}")
        return None
