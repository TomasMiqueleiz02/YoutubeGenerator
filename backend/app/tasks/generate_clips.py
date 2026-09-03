import logging
import os
from datetime import datetime

from celery import shared_task

from app.config import settings
from app.database import SessionLocal
from app.models import Clip, Job, Video
from app.services import ClipService, StorageService

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

        from ai_engine import MomentFinder, Transcriber, VitalityScorer

        # Preferred path: let a language model read the transcript and choose
        # moments by what is being said. Energy heuristics find loud, not
        # interesting, so they are the fallback rather than the default.
        clip_boundaries = []
        moment_details = {}

        transcript = (video.video_metadata or {}).get("transcript")
        if transcript and transcript.get("segments"):
            finder = MomentFinder(model=settings.ANTHROPIC_MODEL)
            moments = finder.find(
                transcript_text=Transcriber.to_timestamped_text(transcript),
                video_duration=video.duration_seconds or 0,
                video_title=video.title,
            )
            for moment in moments:
                clip_boundaries.append(
                    (moment["start"], moment["end"], float(moment["score"]))
                )
                moment_details[(moment["start"], moment["end"])] = moment

            if moments:
                logger.info(
                    "Selected %d moments semantically for video %s",
                    len(moments),
                    video_id,
                )

        # Fallback: audio/video energy peaks
        if not clip_boundaries:
            logger.info("Falling back to signal-based detection for %s", video_id)
            scorer = VitalityScorer()
            combined = scorer.calculate_combined_score(
                np.array(audio_scores),
                np.array(video_scores),
                np.array(content_scores),
            )
            clip_boundaries = scorer.detect_clip_boundaries(
                combined, video.duration_seconds
            )

        if not clip_boundaries:
            logger.warning("No viral moments detected in video %s", video_id)
            video.status = "completed"
            video.processing_progress = 100
            db.commit()
            return

        # Create Clip records
        clip_service = ClipService()
        storage = StorageService()
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

            # Carry across the title and rationale when the model picked this
            # moment, so the user sees why it was chosen.
            detail = moment_details.get((start_time, end_time))
            if detail:
                clip.title = detail["title"]
                clip.caption = detail["hook"]

            # Cut the clip, then hand it to storage so it outlives this
            # container. Worker filesystems are ephemeral and not shared with
            # the API, so a local path alone would leave the clip unreachable.
            try:
                local_clip = clip_service.cut_clip(
                    video.file_path, clip.id, start_time, end_time, vertical=True
                )
                local_thumb = clip_service.generate_thumbnail(
                    local_clip, clip.id, at_second=1.0
                )

                clip.file_path = storage.save(local_clip, "clips/%s.mp4" % clip.id)
                clip.thumbnail_path = storage.save(
                    local_thumb, "thumbnails/%s.jpg" % clip.id
                )

                # Local copies are redundant once uploaded to object storage
                if storage.backend == "s3":
                    for stale in (local_clip, local_thumb):
                        try:
                            os.remove(stale)
                        except OSError:
                            pass
            except Exception as e:
                logger.warning("Could not produce clip %s: %s", clip.id, e)
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
