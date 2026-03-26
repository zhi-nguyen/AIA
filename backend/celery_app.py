import os
from celery import Celery

redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "aia_worker",
    broker=redis_url,
    backend=redis_url,
    include=["tasks"]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Ho_Chi_Minh",
    enable_utc=True,
    task_track_started=True,
    broker_connection_retry_on_startup=True,
    beat_schedule={
        "auto-ingest-news-every-6h": {
            "task": "tasks.auto_ingest_news",
            "schedule": 6 * 60 * 60,  # Every 6 hours (21600 seconds)
            "args": ["default_user"],
        },
        "generate-proposals-every-6h": {
            "task": "tasks.generate_user_proposals",
            "schedule": 6 * 60 * 60,  # Every 6 hours
            "args": ["default_user"],
        },
    },
)
