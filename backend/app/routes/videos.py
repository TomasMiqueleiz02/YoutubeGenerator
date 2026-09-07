import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app import time_ranges
from app.models import Job, User, Video
from app.schemas import (
    VideoCreate,
    VideoListResponse,
    VideoReprocess,
    VideoResponse,
)
from app.services import YouTubeService
from app.tasks.analyze_video import analyze_video_task
from app.tasks.download_video import download_video_task

router = APIRouter()


@router.post("/", response_model=VideoResponse)
async def create_video(
    video_create: VideoCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new video entry and start the download pipeline."""
    try:
        yt_service = YouTubeService()
        video_id = yt_service.extract_video_id(str(video_create.youtube_url))

        existing = db.query(Video).filter(
            (Video.user_id == current_user.id)
            & (Video.youtube_video_id == video_id)
        ).first()

        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Video already exists for this user",
            )

        # oEmbed rather than yt-dlp: the API runs on a datacenter IP where
        # YouTube's bot check blocks extraction. Duration arrives later,
        # filled in by the worker that actually downloads the file.
        metadata = yt_service.get_basic_metadata(video_id)

        db_video = Video(
            id=str(uuid.uuid4()),
            user_id=current_user.id,
            youtube_url=str(video_create.youtube_url),
            youtube_video_id=video_id,
            title=metadata.get("title", "Untitled"),
            channel_name=metadata.get("channel", "Unknown"),
            thumbnail_url=metadata.get("thumbnail"),
            duration_seconds=metadata.get("duration", 0),
            # Normalized without a duration to clamp against: oEmbed does not
            # report one, and the worker measures it from the file it
            # downloads. Anything past the end is trimmed there.
            clip_ranges=time_ranges.as_pairs(
                time_ranges.normalize(video_create.ranges)
            )
            or None,
            status="pending",
        )

        db.add(db_video)
        db.commit()
        db.refresh(db_video)

        download_video_task.delay(db_video.id)

        return db_video

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{video_id}/reprocess", response_model=VideoResponse)
async def reprocess_video(
    video_id: str,
    request: VideoReprocess,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Analyze an already downloaded video again, over different spans.

    Worth its own route because the download is the expensive half: the file
    is already on the machine that did it, so pointing the analysis at a
    different stretch costs minutes rather than another copy of the video.

    The existing clips go: they were cut from spans that are no longer the
    ones being asked about, and leaving them mixed in with the new ones makes
    the list impossible to read.
    """
    video = db.query(Video).filter(
        (Video.id == video_id) & (Video.user_id == current_user.id)
    ).first()

    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    if not video.file_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This video has not finished downloading yet",
        )

    if video.status in ("downloading", "processing"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This video is already being processed",
        )

    ranges = time_ranges.normalize(request.ranges, video.duration_seconds)
    if request.ranges and not ranges:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Those spans are unusable: each one needs at least %d seconds "
            "inside the video" % int(time_ranges.MIN_SPAN_SECONDS),
        )

    for clip in list(video.clips):
        db.delete(clip)

    video.clip_ranges = time_ranges.as_pairs(ranges) or None
    video.status = "downloaded"
    video.processing_progress = 20
    video.error_message = None
    db.commit()
    db.refresh(video)

    analyze_video_task.delay(video.id)

    return video


@router.get("/{video_id}", response_model=VideoResponse)
async def get_video(
    video_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get video details."""
    video = db.query(Video).filter(
        (Video.id == video_id) & (Video.user_id == current_user.id)
    ).first()

    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    return video


@router.get("/", response_model=VideoListResponse)
async def list_videos(
    skip: int = 0,
    limit: int = 10,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List user's videos."""
    videos = db.query(Video).filter(
        Video.user_id == current_user.id
    ).offset(skip).limit(limit).all()

    total = db.query(Video).filter(Video.user_id == current_user.id).count()

    return VideoListResponse(videos=videos, total=total)


@router.delete("/{video_id}")
async def delete_video(
    video_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a video and all its clips."""
    video = db.query(Video).filter(
        (Video.id == video_id) & (Video.user_id == current_user.id)
    ).first()

    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    db.delete(video)
    db.commit()

    return {"message": "Video deleted"}
