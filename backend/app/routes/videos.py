import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import Job, User, Video
from app.schemas import VideoCreate, VideoListResponse, VideoResponse
from app.services import YouTubeService
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

        metadata = yt_service.get_video_metadata(video_id)

        db_video = Video(
            id=str(uuid.uuid4()),
            user_id=current_user.id,
            youtube_url=str(video_create.youtube_url),
            youtube_video_id=video_id,
            title=metadata.get("title", "Untitled"),
            channel_name=metadata.get("channel", "Unknown"),
            thumbnail_url=metadata.get("thumbnail"),
            duration_seconds=metadata.get("duration", 0),
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
