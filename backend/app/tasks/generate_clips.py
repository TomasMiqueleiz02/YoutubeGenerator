import logging
from datetime import datetime

from celery import shared_task

from app.database import SessionLocal
from app.models import Clip, Job, Video
from app.services import ClipService

logger = logging.getLogger(__name__)


@shared_task(bind=True, name="tasks.generate_clips")
def generate_clips_task(self, video_id: str):
    """Generate clip timestamps using the virality scorer, create clip records."""
    db = SessionLocal()
    video = None
    try:
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video or not video.video_metadata:
            logger.error("Video not analyzed: %s", video_id)
            return

        # Load scores from metadata
        audio_scores = video.video_metadata.get("audio_scores", [])
        video_scores = video.video_metadata.get("video_scores", [])
        content_scores = video.video_metadata.get("content_scores", [])

        if not all([audio_scores, video_scores, content_scores]):
            logger.error("Incomplete analysis for video %s", video_id)
            return

        import numpy as np

        from ai_engine import VitalityScorer

        # Combine scores
        scorer = VitalityScorer()
        combined = scorer.calculate_combined_score(
            np.array(audio_scores),
            np.array(video_scores),
            np.array(content_scores),
        )

        # Find clip boundaries
        clip_boundaries = scorer.detect_clip_boundaries(combined, video.duration_seconds)

        if not clip_boundaries:
            logger.warning("No viral moments detected in video %s", video_id)
            video.status = "completed"
            video.processing_progress = 100
            db.commit()
            return

        # Create Clip records
        clip_service = ClipService()
        for start_time, end_time, virality_score in clip_boundaries:
            clip = Clip(
                video_id=video_id,
                start_time=start_time,
                end_time=end_time,
                duration=end_time - start_time,
                virality_score=virality_score,
                audio_score=float(
                    np.mean(audio_scores[int(start_time) : int(end_time)])
                    if start_time < len(audio_scores)
                    else 0
                ),
                video_score=float(
                    np.mean(video_scores[int(start_time) : int(end_time)])
                    if start_time < len(video_scores)
                    else 0
                ),
                content_score=float(
                    np.mean(content_scores[int(start_time) : int(end_time)])
                    if start_time < len(content_scores)
                    else 0
                ),
                status="generated",
            )

            # Cut the clip
            try:
                clip.file_path = clip_service.cut_clip(
                    video.file_path, clip.id, start_time, end_time, vertical=True
                )
                # Generate thumbnail
                clip.thumbnail_path = clip_service.generate_thumbnail(
                    clip.file_path, clip.id, at_second=1.0
                )
            except Exception as e:
                logger.warning("Could not cut clip %s: %s", clip.id, e)
                clip.file_path = None
                clip.thumbnail_path = None

            db.add(clip)

        video.status = "completed"
        video.processing_progress = 100
        db.commit()

        logger.info("Generated %d clips for video %s", len(clip_boundaries), video_id)

    except Exception as exc:
        logger.exception("Error generating clips for video %s", video_id)
        db.rollback()
        if video is not None:
            video.status = "error"
            video.error_message = str(exc)[:500]
        db.commit()
        raise
    finally:
        db.close()
