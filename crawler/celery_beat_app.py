import os
from celery import Celery

redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Dedicated Celery app for the News Crawler Beat service.
# This app is intentionally separate from the main backend Celery app
# so the crawler service can be deployed, scaled, and restarted independently.
crawler_celery_app = Celery(
    "aia_crawler",
    broker=redis_url,
    backend=redis_url,
    include=["crawler_tasks"],  # only loads crawler tasks — no chat/TTS/graph
)

crawler_celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Ho_Chi_Minh",
    enable_utc=True,
    task_track_started=True,
    broker_connection_retry_on_startup=True,
    # ── Beat schedule ─────────────────────────────────────────────────────────
    # Both tasks run every 6 hours. They are queued to the "crawler" queue
    # so the dedicated crawler-worker container picks them up.
    beat_schedule={
        "auto-ingest-news-every-6h": {
            "task": "crawler_tasks.auto_ingest_news",
            "schedule": 6 * 60 * 60,   # 21600 seconds
            "args": ["default_user"],
            "options": {"queue": "crawler"},
        },
        "generate-proposals-every-6h": {
            "task": "crawler_tasks.generate_user_proposals",
            "schedule": 6 * 60 * 60,   # 21600 seconds
            "args": ["default_user"],
            "options": {"queue": "crawler"},
        },
    },
    # Route all crawler tasks to a dedicated queue so
    # the main celery-worker never picks them up
    task_routes={
        "crawler_tasks.*": {"queue": "crawler"},
    },
)
