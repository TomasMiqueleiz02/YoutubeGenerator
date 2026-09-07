import os

from celery import Celery
from celery.signals import worker_ready, worker_shutdown

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

    # How long Redis waits before deciding a claimed task was abandoned. This
    # has to stay above the longest a task can legitimately run: analysis of a
    # long video passes five minutes easily, and anything shorter than the run
    # time hands a still-running task to a second worker. Recovery does not
    # depend on this any more (see app/tasks/recovery.py), so it is set for
    # safety rather than for speed.
    broker_transport_options={"visibility_timeout": 60 * 60},
    result_backend_transport_options={"visibility_timeout": 60 * 60},

    # One video at a time per worker: analysis is CPU-bound, so overlapping
    # jobs slow every one of them down rather than finishing any sooner.
    worker_prefetch_multiplier=1,
)


@worker_ready.connect
def _on_worker_ready(sender=None, **_):
    """
    Requeue whatever a previous worker died holding, then start beating.

    The sweep runs on its own thread, after a pause. It has to ask the other
    workers what they are holding before it moves anything, and that answer
    travels over the same broker: asking the instant this worker goes ready
    got no reply at all, which the sweep can only read as "cannot tell", and
    then it leaves the orphans alone. A few seconds of delay costs nothing
    and makes the difference between recovering a stuck video and skipping
    it.
    """
    import threading
    import time

    from app.tasks.heartbeat import start_heartbeat
    from app.tasks.recovery import restore_orphaned_tasks

    app = sender.app if sender is not None else celery_app
    started = time.time()

    def sweep():
        time.sleep(5)
        # Nothing claimed after this worker came up can be an orphan.
        restore_orphaned_tasks(app, claimed_before=started)

    threading.Thread(target=sweep, name="orphan-recovery", daemon=True).start()
    start_heartbeat(app)


@worker_shutdown.connect
def _clear_heartbeat(sender=None, **_):
    """Say goodbye, so the page shows the worker down the moment it stops."""
    from app.tasks.heartbeat import clear_heartbeat

    clear_heartbeat(getattr(sender, "app", None) or celery_app)
