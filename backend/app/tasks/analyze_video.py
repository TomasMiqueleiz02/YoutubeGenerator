import logging
from datetime import datetime

from celery import shared_task

from app.database import SessionLocal
from app.models import Job, Video

logger = logging.getLogger(__name__)


@shared_task(bind=True, name="tasks.analyze_video")
def analyze_video_task(self, video_id: str):
    """Run the audio, video and content analyzers over a downloaded video."""
    db = SessionLocal()
    video = None
    jobs = {}
    try:
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video or not video.file_path:
            logger.error("Video missing or not downloaded: %s", video_id)
            return

        video.status = "processing"
        db.commit()

        # Imported lazily so the web process never loads the ML stack
        from ai_engine import AudioAnalyzer, ContentAnalyzer, VideoAnalyzer

        analyzers = [
            ("analyze_audio", AudioAnalyzer, 30),
            ("analyze_video", VideoAnalyzer, 45),
            ("analyze_content", ContentAnalyzer, 60),
        ]

        scores = {}
        for task_type, analyzer_cls, progress in analyzers:
            job = Job(
                video_id=video_id,
                task_type=task_type,
                status="processing",
                started_at=datetime.utcnow(),
            )
            db.add(job)
            db.commit()
            jobs[task_type] = job

            analyzer = analyzer_cls(video.file_path)
            scores[task_type] = analyzer.analyze()

            release = getattr(analyzer, "release", None)
            if callable(release):
                release()

            job.status = "completed"
            job.completed_at = datetime.utcnow()
            video.processing_progress = progress
            db.commit()

            logger.info("Finished %s for video %s", task_type, video_id)

        video.video_metadata = {
            **(video.video_metadata or {}),
            "audio_scores": scores["analyze_audio"].tolist(),
            "video_scores": scores["analyze_video"].tolist(),
            "content_scores": scores["analyze_content"].tolist(),
        }
        video.status = "analyzed"
        video.processing_progress = 65
        db.commit()

        logger.info("Video analyzed: %s", video_id)

        from app.tasks.generate_clips import generate_clips_task

        generate_clips_task.delay(video_id)

    except Exception as exc:
        logger.exception("Error analyzing video %s", video_id)
        db.rollback()
        _mark_failed(db, video, jobs, str(exc))
        raise
    finally:
        db.close()


def _mark_failed(db, video, jobs, message: str):
    try:
        if video is not None:
            video.status = "error"
            video.error_message = message[:500]
        for job in jobs.values():
            if job.status != "completed":
                job.status = "failed"
                job.error_message = message
                job.completed_at = datetime.utcnow()
        db.commit()
    except Exception:
        logger.exception("Could not persist failure state")
        db.rollback()
