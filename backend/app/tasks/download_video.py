import logging
from datetime import datetime

from celery import shared_task

from app.database import SessionLocal
from app.models import Job, Video
from app.services import YouTubeService

logger = logging.getLogger(__name__)


@shared_task(bind=True, name="tasks.download_video")
def download_video_task(self, video_id: str):
    """Download a video from YouTube, then hand off to analysis."""
    db = SessionLocal()
    video = None
    job = None
    try:
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            logger.error("Video not found: %s", video_id)
            return

        job = Job(
            video_id=video_id,
            task_type="download",
            status="processing",
            celery_task_id=self.request.id,
            started_at=datetime.utcnow(),
        )
        db.add(job)

        video.status = "downloading"
        video.processing_progress = 5
        db.commit()

        service = YouTubeService()
        file_path = service.download_video(video.youtube_url, video.youtube_video_id)

        video.file_path = file_path
        video.status = "downloaded"
        video.processing_progress = 20
        job.status = "completed"
        job.completed_at = datetime.utcnow()
        db.commit()

        logger.info("Video downloaded: %s", video_id)

        from app.tasks.analyze_video import analyze_video_task

        analyze_video_task.delay(video_id)

    except Exception as exc:
        logger.exception("Error downloading video %s", video_id)
        db.rollback()
        _mark_failed(db, video, job, str(exc))
        raise
    finally:
        db.close()


def _mark_failed(db, video, job, message: str):
    """Record the failure without hiding the original exception."""
    try:
        if video is not None:
            video.status = "error"
            video.error_message = message[:500]
        if job is not None:
            job.status = "failed"
            job.error_message = message
            job.completed_at = datetime.utcnow()
        db.commit()
    except Exception:
        logger.exception("Could not persist failure state")
        db.rollback()
