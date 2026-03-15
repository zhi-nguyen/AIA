"""
news_tools.py - News Fetcher Tools
Thu thập tin tức từ RSS feeds và tìm kiếm theo keyword

Chiến lược tìm kiếm (2 tầng):
1. Google News RSS Search — tìm kiếm theo keyword người dùng nhập
2. RSS feeds cố định — nguồn tin mặc định khi không có keyword cụ thể
"""

import feedparser
import httpx
from bs4 import BeautifulSoup
from typing import Optional
from urllib.parse import quote
import json
import re

from llm.gemini_client import get_gemini_client
from llm.prompts import NEWS_SUMMARY_PROMPT


# === Nguồn tin RSS mặc định ===
DEFAULT_RSS_FEEDS = {
    "VnExpress": "https://vnexpress.net/rss/tin-moi-nhat.rss",
    "VnExpress Công nghệ": "https://vnexpress.net/rss/so-hoa.rss",
    "VnExpress Thế giới": "https://vnexpress.net/rss/the-gioi.rss",
    "Tuổi Trẻ": "https://tuoitre.vn/rss/tin-moi-nhat.rss",
    "TechCrunch AI": "https://techcrunch.com/category/artificial-intelligence/feed/",
}

# Nguồn tin theo chủ đề
TOPIC_FEEDS = {
    "ai": [
        ("VnExpress Công nghệ", "https://vnexpress.net/rss/so-hoa.rss"),
        ("TechCrunch AI", "https://techcrunch.com/category/artificial-intelligence/feed/"),
    ],
    "tech": [
        ("VnExpress Công nghệ", "https://vnexpress.net/rss/so-hoa.rss"),
        ("TechCrunch", "https://techcrunch.com/feed/"),
    ],
    "vietnam": [
        ("VnExpress", "https://vnexpress.net/rss/tin-moi-nhat.rss"),
        ("Tuổi Trẻ", "https://tuoitre.vn/rss/tin-moi-nhat.rss"),
    ],
    "world": [
        ("VnExpress Thế giới", "https://vnexpress.net/rss/the-gioi.rss"),
    ],
    "general": [
        ("VnExpress", "https://vnexpress.net/rss/tin-moi-nhat.rss"),
    ],
}


def _detect_topic(query: str) -> str:
    """Phân loại topic từ query text"""
    lower = query.lower()
    if any(kw in lower for kw in ["ai", "trí tuệ nhân tạo", "machine learning", "chatgpt", "gemini", "llm"]):
        return "ai"
    elif any(kw in lower for kw in ["công nghệ", "tech", "lập trình", "coding", "software"]):
        return "tech"
    elif any(kw in lower for kw in ["việt nam", "trong nước", "thời sự nội địa"]):
        return "vietnam"
    elif any(kw in lower for kw in ["thế giới", "quốc tế", "chiến sự", "ukraine", "trung đông", "gaza", "war"]):
        return "world"
    return "general"


def _has_specific_keyword(query: str) -> bool:
    """
    Kiểm tra xem query có chứa keyword cụ thể đáng tìm kiếm không.
    VD: "tin tức hôm nay" → False (chung chung)
        "Chiến sự Trung Đông" → True (cụ thể)
    """
    lower = query.lower()
    # Các cụm từ chung chung không cần search
    generic_phrases = [
        "tin tức hôm nay", "tin mới", "cập nhật tin", "có gì mới",
        "tin tức mới nhất", "news today", "latest news",
        "tin tức", "đọc tin", "xem tin",
    ]
    # Nếu query CHÍNH XÁC là một trong các cụm chung chung → không search
    for phrase in generic_phrases:
        if lower.strip() == phrase:
            return False

    # Nếu query dài hơn 2 từ và không nằm trong danh sách chung → có keyword cụ thể
    words = query.strip().split()
    return len(words) >= 2


def _extract_search_keywords(query: str) -> str:
    """
    Trích xuất keyword tìm kiếm từ query.
    Bỏ các từ phụ như "tìm tin", "tin tức về", "cho tôi biết"...
    """
    lower = query.lower()
    # Bỏ các prefix phổ biến
    prefixes = [
        "tìm tin tức về", "tìm tin tức liên quan",
        "tìm tin về", "tin tức về", "tin tức liên quan",
        "cập nhật về", "cho tôi biết về",
        "tìm kiếm", "search for", "news about",
        "tìm tin", "đọc tin về",
    ]
    result = lower
    for prefix in sorted(prefixes, key=len, reverse=True):
        if result.startswith(prefix):
            result = result[len(prefix):].strip()
            break

    return result.strip() or query.strip()


def _clean_google_news_title(title: str, source: str) -> str:
    """
    Google News RSS title = 'Tiêu đề bài viết - Tên Báo'
    Bỏ phần ' - Tên Báo' ở cuối vì source đã hiển thị riêng.
    """
    # Thử bỏ suffix " - Source"
    suffix = f" - {source}"
    if title.endswith(suffix):
        return title[:-len(suffix)].strip()
    
    # Fallback: tìm " - " cuối cùng và bỏ
    last_dash = title.rfind(" - ")
    if last_dash > 20:  # Chỉ cắt nếu phần trước đủ dài
        return title[:last_dash].strip()
    
    return title


def _clean_summary(summary: str, title: str) -> str:
    """
    Bỏ phần lặp title khỏi summary.
    Google News RSS summary thường = 'Tiêu đềTên báo' (lặp lại).
    """
    if not summary:
        return ""
    
    # Nếu summary gần giống title → bỏ luôn  
    clean_title = title.lower().replace(" ", "")
    clean_summary = summary.lower().replace(" ", "")
    if clean_summary.startswith(clean_title[:30]):
        return ""
    
    return summary


def search_google_news(query: str, limit: int = 10, lang: str = "vi") -> list[dict]:
    """
    Tìm kiếm tin tức qua Google News RSS, giới hạn trong 24h qua (when:1d).
    """
    # Thêm operator when:1d để chỉ lấy tin mới
    search_query = f"{query} when:1d"
    encoded_query = quote(search_query)
    
    if lang == "vi":
        url = f"https://news.google.com/rss/search?q={encoded_query}&hl=vi&gl=VN&ceid=VN:vi"
    else:
        url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en&gl=US&ceid=US:en"

    print(f"[NewsTools] Searching Google News: {search_query}")
    
    try:
        feed = feedparser.parse(url)
        articles = []

        for entry in feed.entries[:limit]:
            # Lấy nguồn tin (source) TRƯỚC để dùng clean title
            source = "Google News"
            if hasattr(entry, "source"):
                source = entry.source.get("title", "Google News")

            # Clean title — bỏ suffix "- Tên Báo"
            raw_title = entry.get("title", "Không có tiêu đề")
            title = _clean_google_news_title(raw_title, source)

            # Google News RSS summary thường chỉ lặp lại title
            summary = ""
            if hasattr(entry, "summary"):
                soup = BeautifulSoup(entry.summary, "html.parser")
                raw_summary = soup.get_text(strip=True)[:500]
                summary = _clean_summary(raw_summary, title)

            published = getattr(entry, "published", "")

            articles.append({
                "title": title,
                "source": source,
                "url": entry.get("link", ""),
                "summary": summary,
                "published": published,
            })

        print(f"[NewsTools] Found {len(articles)} articles from Google News")
        return articles

    except Exception as e:
        print(f"[NewsTools] Lỗi search Google News: {e}")
        return []


def fetch_rss_news(feed_url: str, source_name: str, limit: int = 5) -> list[dict]:
    """
    Fetch tin tức từ một RSS feed cố định.
    """
    try:
        feed = feedparser.parse(feed_url)
        articles = []

        for entry in feed.entries[:limit]:
            summary = ""
            if hasattr(entry, "summary"):
                soup = BeautifulSoup(entry.summary, "html.parser")
                summary = soup.get_text(strip=True)[:500]
            elif hasattr(entry, "description"):
                soup = BeautifulSoup(entry.description, "html.parser")
                summary = soup.get_text(strip=True)[:500]

            published = ""
            if hasattr(entry, "published"):
                published = entry.published
            elif hasattr(entry, "updated"):
                published = entry.updated

            articles.append({
                "title": entry.get("title", "Không có tiêu đề"),
                "source": source_name,
                "url": entry.get("link", ""),
                "summary": summary,
                "published": published,
            })

        return articles

    except Exception as e:
        print(f"[NewsTools] Lỗi fetch RSS {source_name}: {e}")
        return []


def fetch_news(query: str = "", limit: int = 10) -> list[dict]:
    """
    Fetch tin tức — tự động chọn chiến lược:
    
    1. Nếu query có keyword cụ thể (VD: "Chiến sự Trung Đông")
       → Tìm kiếm qua Google News RSS
       
    2. Nếu query chung chung (VD: "tin tức hôm nay")
       → Lấy từ RSS feeds cố định theo topic
    """
    all_articles = []

    if query and _has_specific_keyword(query):
        # === Chiến lược 1: Tìm kiếm theo keyword ===
        search_keywords = _extract_search_keywords(query)
        print(f"[NewsTools] Strategy: SEARCH with keywords: '{search_keywords}'")
        
        # Tìm trên Google News (tiếng Việt)
        articles = search_google_news(search_keywords, limit=limit, lang="vi")
        all_articles.extend(articles)

        # Nếu không đủ kết quả, thử tiếng Anh
        if len(all_articles) < 3:
            en_articles = search_google_news(search_keywords, limit=5, lang="en")
            all_articles.extend(en_articles)

    else:
        # === Chiến lược 2: RSS feeds cố định theo topic ===
        topic = _detect_topic(query)
        feeds = TOPIC_FEEDS.get(topic, TOPIC_FEEDS["general"])
        print(f"[NewsTools] Strategy: RSS FEEDS for topic: {topic}")

        per_feed_limit = max(limit // len(feeds), 3)
        for source_name, feed_url in feeds:
            articles = fetch_rss_news(feed_url, source_name, limit=per_feed_limit)
            all_articles.extend(articles)

    print(f"[NewsTools] Total articles fetched: {len(all_articles)}")
    return all_articles[:limit]


def summarize_news(articles: list[dict], query: str, user_preferences: str = "") -> dict:
    """
    Tóm tắt tin tức bằng Gemini Flash.
    """
    if not articles:
        return {"news": [], "message": "Không tìm thấy tin tức phù hợp."}

    client = get_gemini_client()

    # Chuẩn bị articles text
    articles_text = ""
    for i, article in enumerate(articles, 1):
        articles_text += f"\n--- Bài {i} ---\n"
        articles_text += f"Tiêu đề: {article['title']}\n"
        articles_text += f"Nguồn: {article['source']}\n"
        articles_text += f"Tóm tắt: {article['summary']}\n"
        articles_text += f"URL: {article['url']}\n"

    prompt = NEWS_SUMMARY_PROMPT.format(
        user_preferences=user_preferences or "Chưa có thông tin",
        query=query,
        articles=articles_text,
    )

    try:
        response = client.generate_flash(prompt)

        # Parse JSON
        clean = response.strip()
        if "```" in clean:
            match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", clean, re.DOTALL)
            if match:
                clean = match.group(1).strip()

        try:
            return json.loads(clean)
        except json.JSONDecodeError:
            return {
                "news": [
                    {
                        "title": a["title"],
                        "source": a["source"],
                        "summary": a["summary"][:200],
                        "url": a["url"],
                    }
                    for a in articles[:5]
                ],
                "raw_summary": response,
            }

    except Exception as e:
        print(f"[NewsTools] Lỗi summarize: {e}")
        return {"news": [], "error": str(e)}
