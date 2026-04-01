import os
from celery import Celery

redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "aia_worker",
    broker=redis_url,
    backend=redis_url,
    include=["tasks"]  # chat, TTS tasks (email assistant now uses Pub/Sub push)
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
        "fetch-weather-data": {
            "task": "tasks.fetch_weather_for_events",
            "schedule": 3600.0,  # Every 1 hour
        },
    },
)
