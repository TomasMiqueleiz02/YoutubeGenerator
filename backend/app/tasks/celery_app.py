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

    # Acknowledge a task only once it finishes, and requeue it if the worker
    # dies mid-run. Without this, closing the worker window (or a crash)
    # silently drops whatever was in flight and the video sits at a partial
    # percentage forever.
    task_acks_late=True,
    task_reject_on_worker_lost=True,

    # One video at a time per worker: analysis is CPU-bound, so overlapping
    # jobs slow every one of them down rather than finishing any sooner.
    worker_prefetch_multiplier=1,
)
