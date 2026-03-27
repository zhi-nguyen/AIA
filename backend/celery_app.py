import os
from celery import Celery

redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "aia_worker",
    broker=redis_url,
    backend=redis_url,
    include=["tasks"]  # chat, TTS tasks only
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Ho_Chi_Minh",
    enable_utc=True,
    task_track_started=True,
    broker_connection_retry_on_startup=True,
    # Note: beat_schedule has been moved to crawler/celery_beat_app.py
    # Main worker only handles: tasks.process_chat, tasks.generate_tts
)
