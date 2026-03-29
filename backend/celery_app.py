import os
from celery import Celery
from celery.schedules import crontab

redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "aia_worker",
    broker=redis_url,
    backend=redis_url,
    include=["tasks"]  # chat, TTS, and email_assistant tasks
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Ho_Chi_Minh",
    enable_utc=True,
    task_track_started=True,
    broker_connection_retry_on_startup=True,
    # Beat schedule — runs hourly_email_assistant every 15 minutes
    beat_schedule={
        "email-assistant-every-15-min": {
            "task": "tasks.hourly_email_assistant",
            "schedule": crontab(minute="*/15"),
            "options": {"queue": "default"},
        },
    },
)

