from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import Clip, User, Video
from app.schemas import ClipListResponse, ClipResponse, ClipUpdate
from app.services import StorageService

router = APIRouter()


@router.get("/video/{video_id}", response_model=ClipListResponse)
async def get_clips_for_video(
    video_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get all clips for a video."""
    video = db.query(Video).filter(
        (Video.id == video_id) & (Video.user_id == current_user.id)
    ).first()

    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    clips = db.query(Clip).filter(Clip.video_id == video_id).all()

    return ClipListResponse(clips=clips, total=len(clips))


@router.get("/{clip_id}", response_model=ClipResponse)
async def get_clip(
    clip_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get clip details."""
    clip = db.query(Clip).join(Video).filter(
        (Clip.id == clip_id) & (Video.user_id == current_user.id)
    ).first()

    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")

    return clip


@router.put("/{clip_id}", response_model=ClipResponse)
async def update_clip(
    clip_id: str,
    clip_update: ClipUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update a clip (title, caption, times)."""
    clip = db.query(Clip).join(Video).filter(
        (Clip.id == clip_id) & (Video.user_id == current_user.id)
    ).first()

    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")

    update_data = clip_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(clip, key, value)

    if clip.start_time and clip.end_time:
        clip.duration = clip.end_time - clip.start_time

    db.commit()
    db.refresh(clip)

    return clip


@router.get("/{clip_id}/media")
async def get_clip_media_urls(
    clip_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Return temporary URLs for a clip's video and thumbnail.

    Stored values are object keys, not URLs, so links are signed on demand and
    never go stale in the database.
    """
    clip = db.query(Clip).join(Video).filter(
        (Clip.id == clip_id) & (Video.user_id == current_user.id)
    ).first()

    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")

    if not clip.file_path:
        raise HTTPException(status_code=404, detail="Clip media not available yet")

    storage = StorageService()
    return {
        "video_url": storage.presigned_url(clip.file_path),
        "thumbnail_url": (
            storage.presigned_url(clip.thumbnail_path) if clip.thumbnail_path else None
        ),
    }


@router.delete("/{clip_id}")
async def delete_clip(
    clip_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a clip."""
    clip = db.query(Clip).join(Video).filter(
        (Clip.id == clip_id) & (Video.user_id == current_user.id)
    ).first()

    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")

    db.delete(clip)
    db.commit()

    return {"message": "Clip deleted"}
