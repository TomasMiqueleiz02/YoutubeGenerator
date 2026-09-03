import os

from celery import Celery

celery_app = Celery(
    "clip_generator",
    broker=os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1"),
    include=[
        "app.tasks.download_video",
        "app.tasks.analyze_video",
        "app.tasks.generate_clips",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=60 * 60,      # hard limit: 1 hour
    task_soft_time_limit=55 * 60,
    worker_max_tasks_per_child=10,  # release memory held by ML models
)
