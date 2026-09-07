import logging
import os
import uuid
from datetime import datetime

from celery import shared_task

from app.config import settings
from app.database import SessionLocal
from app.models import Clip, Job, Video
from app.services import ClipService, StorageService

logger = logging.getLogger(__name__)

# Below this, a model's selection is treated as a failed read of the
# transcript rather than a short list of genuinely good moments.
MIN_LLM_MOMENTS = 3


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

        from app import time_ranges
        from ai_engine import (
            CaptionWriter,
            FaceTracker,
            VideoLayout,
            HeuristicMomentFinder,
            LocalMomentFinder,
            MomentFinder,
            SubtitleGenerator,
            SubtitleStyle,
            Transcriber,
            VitalityScorer,
        )

        ranges = time_ranges.normalize(video.clip_ranges, video.duration_seconds)

        def within_marked_spans(boundaries):
            """
            Drop moments that fall outside the spans marked for clipping.

            A moment counts as inside when its middle is, rather than the
            whole of it: the payoff often runs a few seconds past where
            someone stopped dragging the marker, and cutting that off would
            be worse than letting the clip spill over the edge. A moment that
            merely grazes the span is not kept.
            """
            if not ranges:
                return boundaries

            kept = [
                b for b in boundaries
                if time_ranges.covers(ranges, (b[0] + b[1]) / 2.0)
            ]
            if len(kept) != len(boundaries):
                logger.info(
                    "Dropped %d moment(s) outside %s",
                    len(boundaries) - len(kept),
                    time_ranges.describe(ranges),
                )
            return kept

        # Selection runs on the transcript, so clips are chosen by what is
        # said rather than how loud it gets. Three tiers, best first.
        clip_boundaries = []
        moment_details = {}
        moments = []

        transcript = (video.video_metadata or {}).get("transcript")
        if transcript and transcript.get("segments"):
            # Tier 1: a language model, only when a key is configured
            finder = MomentFinder(model=settings.ANTHROPIC_MODEL)
            if finder.available:
                moments = finder.find(
                    transcript_text=Transcriber.to_timestamped_text(transcript),
                    video_duration=video.duration_seconds or 0,
                    video_title=video.title,
                )
                if moments:
                    logger.info("Selected %d moments via LLM for %s", len(moments), video_id)

            # Tier 2: a model running on this machine. Same prompt and schema
            # as tier 1, no metered API, and still unattended.
            if not moments:
                local = LocalMomentFinder()
                if local.available:
                    moments = local.find(
                        transcript_text=Transcriber.to_timestamped_text(transcript),
                        video_duration=video.duration_seconds or 0,
                        video_title=video.title,
                        # Used to locate each hook in the transcript, since the
                        # model's own timestamps are unreliable.
                        segments=Transcriber.merge_segments(transcript["segments"]),
                    )
                    # A small model handles clean, structured speech well and
                    # messy multi-speaker audio poorly, where it returns a
                    # couple of weak picks. Two thin results should not beat
                    # eight solid heuristic ones, so it has to clear a floor
                    # before it gets to replace them.
                    if 0 < len(moments) < MIN_LLM_MOMENTS:
                        logger.info(
                            "Local model returned only %d moments for %s; "
                            "using heuristics instead",
                            len(moments),
                            video_id,
                        )
                        moments = []
                    elif moments:
                        logger.info(
                            "Selected %d moments via local model for %s",
                            len(moments),
                            video_id,
                        )

            # Tier 3: free text heuristics over the same transcript
            if not moments:
                moments = HeuristicMomentFinder().find(
                    transcript=transcript,
                    video_duration=video.duration_seconds or 0,
                )
                if moments:
                    logger.info(
                        "Selected %d moments heuristically for %s", len(moments), video_id
                    )

            for moment in moments:
                clip_boundaries.append(
                    (moment["start"], moment["end"], float(moment["score"]))
                )
                moment_details[(moment["start"], moment["end"])] = moment

            clip_boundaries = within_marked_spans(clip_boundaries)

        # Fallback: audio/video energy peaks
        if not clip_boundaries:
            logger.info("Falling back to signal-based detection for %s", video_id)
            scorer = VitalityScorer()
            combined = scorer.calculate_combined_score(
                np.array(audio_scores),
                np.array(video_scores),
                np.array(content_scores),
            )
            clip_boundaries = within_marked_spans(
                scorer.detect_clip_boundaries(combined, video.duration_seconds)
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
        face_tracker = FaceTracker()
        # Keep the whole frame by default: cropping to a column loses
        # whatever the subject was reacting to, which is often the point.
        layout = VideoLayout(mode=settings.CLIP_LAYOUT)
        caption_writer = CaptionWriter()
        merged_segments = (
            Transcriber.merge_segments(transcript["segments"])
            if transcript and transcript.get("segments")
            else []
        )
        for start_time, end_time, virality_score in clip_boundaries:
            clip = Clip(
                # Assign the id up front: the column default only fires on
                # insert, and the id names the stored files. Without this every
                # clip is written as "None.mp4" and they overwrite each other.
                id=str(uuid.uuid4()),
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

            # Post text written from what is actually said in this window, so
            # the clip arrives ready to publish rather than needing a caption
            # invented by hand for each one.
            if merged_segments and caption_writer.available:
                spoken = " ".join(
                    seg["text"]
                    for seg in merged_segments
                    if start_time <= seg["start"] < end_time
                )
                written = caption_writer.write(
                    spoken, video.title, (transcript or {}).get("language")
                )
                if written:
                    clip.social_caption = written["title"]
                    clip.hashtags = written["hashtags"]

            # Cut the clip, then hand it to storage so it outlives this
            # container. Worker filesystems are ephemeral and not shared with
            # the API, so a local path alone would leave the clip unreachable.
            try:
                # Word-timed captions, rebased to this clip's start
                subtitles = None
                if transcript and transcript.get("segments"):
                    subtitles = SubtitleGenerator(
                        SubtitleStyle(margin_vertical=layout.caption_margin)
                    ).build(
                        segments=transcript["segments"],
                        clip_start=start_time,
                        clip_end=end_time,
                    )

                # Frame the vertical crop on whoever is talking, instead of
                # blindly taking the middle column of the shot.
                center = None
                if layout.mode == VideoLayout.CROP:
                    try:
                        center = face_tracker.find_crop_center(
                            video.file_path, start_time, end_time
                        )
                    except Exception:
                        logger.warning("Face tracking failed", exc_info=True)
                crop = layout.filter_complex(center)

                local_clip = clip_service.cut_clip(
                    video.file_path,
                    clip.id,
                    start_time,
                    end_time,
                    vertical=True,
                    subtitles_ass=subtitles,
                    crop_filter=crop,
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
