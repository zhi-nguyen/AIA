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
        import httpx
        # Sử dụng httpx để có cơ chế timeout chặn việc bị block vô thời hạn (Hanging)
        resp = httpx.get(url, timeout=10.0, follow_redirects=True)
        feed = feedparser.parse(resp.content)
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
        import httpx
        # Tránh lỗi treo vô thời hạn khi gọi rss không phản hồi
        resp = httpx.get(feed_url, timeout=10.0, follow_redirects=True)
        feed = feedparser.parse(resp.content)
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


def fetch_news(query: str = "", limit: int = 10, is_extracted_query: bool = False) -> list[dict]:
    """
    Fetch tin tức — tự động chọn chiến lược:
    
    1. Nếu is_extracted_query=True: Trực tiếp tìm bằng keyword trên Google News RSS
    2. Nếu is_extracted_query=False: Dùng RSS mặc định (cho câu hỏi chung chung)
    """
    all_articles = []

    if is_extracted_query and query:
        # === Chiến lược 1: Tìm kiếm theo keyword ===
        print(f"[NewsTools] Strategy: SEARCH with keywords: '{query}'")
        
        # Tìm trên Google News (tiếng Việt)
        articles = search_google_news(query, limit=limit, lang="vi")
        all_articles.extend(articles)

        # Nếu không đủ kết quả, thử tiếng Anh
        if len(all_articles) < 3:
            en_articles = search_google_news(query, limit=5, lang="en")
            all_articles.extend(en_articles)

    else:
        # === Chiến lược 2: RSS feeds cố định theo topic ===
        topic = _detect_topic(query)
        feeds = TOPIC_FEEDS.get(topic, TOPIC_FEEDS["general"])
        print(f"[NewsTools] Strategy: RSS FEEDS for topic: {topic}")

        per_feed_limit = max(limit // len(feeds), 3)
        for source_name, feed_url in feeds:
            articles = fetch_rss_news(feed_url, source_name, limit=per_feed_limit)
            if articles:
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

    print(f"[NewsTools] Bắt đầu gọi Agent summarize cho {len(articles)} bài báo...")
    try:
        response = client.generate_flash(prompt, response_mime_type="application/json")
        print(f"[NewsTools] Summarize response received, length: {len(response)}")

        # Parse JSON
        clean = response.strip()
        if "```" in clean:
            match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", clean, re.DOTALL)
            if match:
                clean = match.group(1).strip()
        else:
            # Fallback for models like gemini-2.5-pro that might not use backticks
            start = clean.find('{')
            end = clean.rfind('}')
            if start != -1 and end != -1:
                clean = clean[start:end+1]

        try:
            return json.loads(clean)
        except json.JSONDecodeError as decode_err:
            print(f"[NewsTools] Lỗi JSONDecode Error trong Summarize: {decode_err}\nRaw output: {clean[:200]}")
            
            # --- Tự cứu (Best Effort Extract) dành cho JSON bị cắt ngang ---
            extracted_summary = ""
            # Tìm "summary": "..." một cách lỏng lẻo
            m = re.search(r'"summary"\s*:\s*"([^"]+)"', response)
            if m:
                extracted_summary = m.group(1)
            else:
                # Trường hợp bị cắt đứt giữa chừng chưa đóng ngoặc kép
                m_partial = re.search(r'"summary"\s*:\s*"([^"]*)', response)
                if m_partial:
                    extracted_summary = m_partial.group(1) + "..."
            
            if extracted_summary:
                return {
                    "summary": extracted_summary,
                    "sources": [{"title": a["title"], "source": a["source"], "url": a["url"]} for a in articles[:5]]
                }

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


# ============================================================
# === Vertex AI Search Data Store Ingestion ===
# ============================================================

def parse_gemini_json(raw_text: str) -> list[dict]:
    """
    Trích xuất JSON array từ response text của Gemini.
    Xử lý: markdown fences, text thừa bao quanh JSON, partial output.
    """
    if not raw_text:
        return []

    clean = raw_text.strip()

    # Bỏ markdown code fences nếu có
    if "```" in clean:
        match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", clean, re.DOTALL)
        if match:
            clean = match.group(1).strip()

    # Tìm JSON array [...] hoặc JSON object {...}
    first_brace = clean.find("{")
    first_bracket = clean.find("[")
    
    start = -1
    end = -1
    
    if first_brace != -1 and (first_bracket == -1 or first_brace < first_bracket):
        # JSON object là ngoài cùng
        start = first_brace
        end = clean.rfind("}")
        if start != -1 and end != -1 and end > start:
            clean = "[" + clean[start:end + 1] + "]"
    elif first_bracket != -1:
        # JSON array là ngoài cùng
        start = first_bracket
        end = clean.rfind("]")
        if start != -1 and end != -1 and end > start:
            clean = clean[start:end + 1]

    try:
        data = json.loads(clean, strict=False)
        if isinstance(data, list):
            return data
        elif isinstance(data, dict):
            return [data]
        return []
    except json.JSONDecodeError as e:
        print(f"[NewsTools] parse_gemini_json error: {e}\nRaw: {clean[:300]}")
        return []


def push_to_vertex_search(document: dict, data_store_id: str = None) -> bool:
    """
    Đẩy một document vào Vertex AI Search data store.
    
    Args:
        document: Dict chứa ít nhất {"id", "title", "content", "metadata"}
        data_store_id: ID của data store (mặc định lấy từ config)
    
    Returns:
        True nếu thành công, False nếu thất bại
    """
    from google.cloud import discoveryengine_v1 as discoveryengine
    from google.oauth2 import service_account
    from config import get_settings

    settings = get_settings()
    ds_id = data_store_id or settings.vertex_search_data_store_id
    project_id = settings.vertex_project_id
    location = "global"  # Vertex AI Search data stores mặc định ở global

    try:
        # Authenticate với data-store-key.json riêng
        credentials = service_account.Credentials.from_service_account_file(
            settings.data_store_credentials_path,
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )

        client = discoveryengine.DocumentServiceClient(credentials=credentials)

        # Parent path: projects/{project}/locations/{location}/dataStores/{ds}/branches/default_branch
        parent = client.branch_path(
            project=project_id,
            location=location,
            data_store=ds_id,
            branch="default_branch",
        )

        # Build document: content as raw bytes, metadata as struct_data
        metadata = document.get("metadata", {})

        doc = discoveryengine.Document(
            id=document.get("id", ""),
            content=discoveryengine.Document.Content(
                raw_bytes=document.get("content", "").encode("utf-8"),
                mime_type="text/plain",
            ),
            struct_data={
                "title": document.get("title", ""),
                "metadata": {
                    "source": metadata.get("source", "Unknown"),
                    "tag": metadata.get("tag", "General"),
                    "url": metadata.get("url", ""),
                    "published": metadata.get("published", ""),
                },
            },
        )

        result = client.create_document(
            parent=parent,
            document=doc,
            document_id=document.get("id", ""),
        )

        print(f"[NewsTools] Pushed to data store: {document.get('title', '')[:60]}")
        return True

    except Exception as e:
        # If document already exists (ALREADY_EXISTS), try update instead of create
        if "ALREADY_EXISTS" in str(e) or "409" in str(e):
            try:
                doc_name = f"{parent}/documents/{document.get('id', '')}"
                metadata = document.get("metadata", {})
                doc = discoveryengine.Document(
                    name=doc_name,
                    content=discoveryengine.Document.Content(
                        raw_bytes=document.get("content", "").encode("utf-8"),
                        mime_type="text/plain",
                    ),
                    struct_data={
                        "title": document.get("title", ""),
                        "metadata": {
                            "source": metadata.get("source", "Unknown"),
                            "tag": metadata.get("tag", "General"),
                            "url": metadata.get("url", ""),
                            "published": metadata.get("published", ""),
                        },
                    },
                )
                client.update_document(document=doc)
                print(f"[NewsTools] Updated existing doc: {document.get('title', '')[:60]}")
                return True
            except Exception as update_err:
                print(f"[NewsTools] Update failed: {update_err}")
                return False

        print(f"[NewsTools] Push to data store failed: {e}")
        return False


def search_vertex_store(query: str, top_k: int = 10, data_store_id: str = None) -> list[dict]:
    """
    Tìm kiếm tin tức trong Vertex AI Search data store.

    Args:
        query: Chuỗi tìm kiếm (sở thích / tag của user)
        top_k: Số document tối đa trả về
        data_store_id: ID data store (mặc định lấy từ config)

    Returns:
        Danh sách document dạng [{"id", "title", "content", "metadata"}]
    """
    from google.cloud import discoveryengine_v1 as discoveryengine
    from google.oauth2 import service_account
    from config import get_settings

    settings = get_settings()
    ds_id = data_store_id or settings.vertex_search_data_store_id
    project_id = settings.vertex_project_id
    location = "global"

    try:
        credentials = service_account.Credentials.from_service_account_file(
            settings.data_store_credentials_path,
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )

        client = discoveryengine.SearchServiceClient(credentials=credentials)

        serving_config = (
            f"projects/{project_id}/locations/{location}"
            f"/dataStores/{ds_id}/servingConfigs/default_search"
        )

        request = discoveryengine.SearchRequest(
            serving_config=serving_config,
            query=query,
            page_size=top_k,
        )

        response = client.search(request)

        results: list[dict] = []
        for result in response.results:
            doc = result.document
            doc_data: dict = {}

            # Read from json_data (string JSON) first
            if doc.json_data:
                try:
                    doc_data = json.loads(doc.json_data)
                except json.JSONDecodeError:
                    pass

            # Fallback: read from struct_data (used in NO_CONTENT stores)
            if not doc_data and doc.struct_data:
                doc_data = dict(doc.struct_data)

            # Rebuild metadata: support both flat-struct and nested metadata
            if "metadata" in doc_data and hasattr(doc_data["metadata"], "items"):
                metadata = dict(doc_data["metadata"])
            else:
                # Fields stored flat by push_to_vertex_search in NO_CONTENT mode
                metadata = {
                    "tag": doc_data.get("tag", ""),
                    "source": doc_data.get("source", ""),
                    "url": doc_data.get("url", ""),
                    "published": doc_data.get("published", ""),
                }

            results.append({
                "id": doc.id or "",
                "title": doc_data.get("title", ""),
                "content": doc_data.get("content", ""),
                "metadata": metadata,
            })

        print(f"[NewsTools] 🔍 Vertex Search returned {len(results)} results for: '{query[:50]}'")
        return results

    except Exception as e:
        print(f"[NewsTools] ❌ Vertex Search failed: {e}")
        return []

