# crawler/crawler_tasks.py
"""
News Crawler Tasks — runs in the dedicated crawler-worker/crawler-beat containers.

Tasks:
  - auto_ingest_news:        Fetches news via Gemini Search Grounding → Vertex AI Search
  - generate_user_proposals: Reads news from Vertex AI Search → Gemini synthesis → WebSocket
"""

import json
import os
import uuid

from celery_beat_app import crawler_celery_app


# ─────────────────────────────────────────────────────────────────────────────
# Task: auto_ingest_news
# ─────────────────────────────────────────────────────────────────────────────
@crawler_celery_app.task(bind=True, name="crawler_tasks.auto_ingest_news")
def auto_ingest_news(self, user_id: str = "default_user"):
    """
    Periodic task: Tự động thu thập tin tức bằng Gemini + Google Search Grounding,
    dựa trên profile người dùng, sau đó đẩy vào Vertex AI Search data store.

    Schedule: every 6 hours (defined in celery_beat_app.py)
    Queue:    crawler
    """
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

    from llm.gemini_client import get_gemini_client
    from tools.news_tools import parse_gemini_json, push_to_vertex_search
    from memory.user_context import get_user_profile

    profile = get_user_profile(user_id)
    categories: list[str] = []

    if profile:
        occupation = profile.get("occupation", "")
        interests = profile.get("interests", [])
        news_sources = profile.get("preferred_news_sources", [])

        for interest in interests:
            categories.append(f"Tin tức mới nhất về {interest}")
        if occupation:
            categories.append(f"Xu hướng và quy định mới trong lĩnh vực {occupation}")
        for src in news_sources:
            categories.append(f"Cập nhật mới nhất về {src}")

    if not categories:
        categories = [
            "Công nghệ AI và ứng dụng thực tiễn",
            "Xu hướng chuyển đổi số doanh nghiệp",
            "Tin tức pháp luật và quy định mới",
            "Kinh tế và thị trường tài chính",
            "Khoa học công nghệ nổi bật",
        ]

    client = get_gemini_client()
    total_pushed = 0
    total_failed = 0

    for cat in categories:
        print(f"\n[AutoIngest] 🔍 Processing category: {cat}")

        prompt = f"""
Sử dụng Google Search để tìm 3 tin tức quan trọng và mới nhất hôm nay về: '{cat}'.
Tóm tắt và trả về dưới dạng JSON array chuẩn:
[
  {{
    "id": "<unique-id>",
    "title": "Tiêu đề bài viết",
    "content": "Tóm tắt nội dung chính (200-400 từ)",
    "metadata": {{
      "domain": "{cat}",
      "tag": "{cat}",
      "source": "Tên nguồn tin",
      "url": "URL gốc nếu có"
    }}
  }}
]

Quy tắc:
- Mỗi "id" phải là unique string (dùng slug từ tiêu đề).
- "content" phải là bản tóm tắt đầy đủ, có giá trị thông tin.
- Chỉ trả về JSON, không thêm text giải thích.
"""

        try:
            response = client.generate_search_grounded(prompt)
            news_data = parse_gemini_json(response)

            if not news_data:
                print(f"[AutoIngest] ⚠️ No valid JSON for category: {cat}")
                continue

            print(f"[AutoIngest] 📰 Found {len(news_data)} articles for: {cat}")

            for news in news_data:
                if not news.get("id"):
                    news["id"] = str(uuid.uuid4())[:8]
                if "metadata" not in news:
                    news["metadata"] = {"domain": "general", "tag": cat}

                success = push_to_vertex_search(news)
                if success:
                    total_pushed += 1
                else:
                    total_failed += 1

        except Exception as e:
            print(f"[AutoIngest] ❌ Error processing category '{cat}': {e}")
            total_failed += 1

    summary = f"[AutoIngest] ✅ Completed: {total_pushed} pushed, {total_failed} failed"
    print(summary)
    return {"pushed": total_pushed, "failed": total_failed}


# ─────────────────────────────────────────────────────────────────────────────
# Task: generate_user_proposals
# ─────────────────────────────────────────────────────────────────────────────
@crawler_celery_app.task(bind=True, name="crawler_tasks.generate_user_proposals")
def generate_user_proposals(self, user_id: str = "default_user"):
    """
    Periodic task: Tạo đề xuất hành động dựa trên profile người dùng
    và tin tức từ Vertex AI Search, sau đó push qua WebSocket (Redis PubSub).

    Schedule: every 6 hours (defined in celery_beat_app.py)
    Queue:    crawler
    """
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

    import redis as redis_lib
    from agents.news_agent import generate_proposal_for_user

    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    try:
        print(f"\n[ProposalTask] 🚀 Starting proposal generation for user: {user_id}")

        proposal = generate_proposal_for_user(user_id)

        if not proposal:
            print(f"[ProposalTask] ℹ️ No proposal generated for user: {user_id}")
            return {"status": "no_proposal", "user_id": user_id}

        # Push to frontend via Redis PubSub
        try:
            r = redis_lib.from_url(redis_url)
            pub_data = {
                "type": "new_proposal",
                "user_id": user_id,
                "task_id": self.request.id,
                "proposal": proposal,
            }
            r.publish("aia_ws_messages", json.dumps(pub_data, ensure_ascii=False))
            print(f"[ProposalTask] ✅ Proposal pushed to WebSocket: {proposal.get('title', '')[:60]}")
        except Exception as redis_e:
            print(f"[ProposalTask] ❌ Redis publish error: {redis_e}")

        return {
            "status": "success",
            "user_id": user_id,
            "proposal_title": proposal.get("title", ""),
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"[ProposalTask] ❌ Error: {e}")
        return {"status": "error", "error": str(e)}
