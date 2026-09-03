from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import Clip, User, Video
from app.services import PublishService

router = APIRouter()


@router.post("/{clip_id}/tiktok")
async def publish_to_tiktok(
    clip_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Publish clip to TikTok."""
    clip = db.query(Clip).join(Video).filter(
        (Clip.id == clip_id) & (Video.user_id == current_user.id)
    ).first()

    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")

    if not clip.file_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Clip file not available",
        )

    if not current_user.tiktok_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="TikTok account not connected",
        )

    try:
        publish_service = PublishService()
        result = publish_service.publish_to_tiktok(
            clip_file_path=clip.file_path,
            title=clip.title,
            caption=clip.caption,
            access_token=current_user.tiktok_token,
        )

        clip.tiktok_post_id = result["post_id"]
        if "tiktok" not in clip.published_platforms:
            clip.published_platforms.append("tiktok")
        clip.status = "published"

        db.commit()

        return {"status": "success", "post_id": result["post_id"]}

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{clip_id}/instagram")
async def publish_to_instagram(
    clip_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Publish clip to Instagram Reels."""
    clip = db.query(Clip).join(Video).filter(
        (Clip.id == clip_id) & (Video.user_id == current_user.id)
    ).first()

    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")

    if not clip.file_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Clip file not available",
        )

    if not current_user.instagram_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Instagram account not connected",
        )

    try:
        publish_service = PublishService()
        result = publish_service.publish_to_instagram(
            clip_file_path=clip.file_path,
            caption=clip.caption,
            access_token=current_user.instagram_token,
        )

        clip.instagram_post_id = result["post_id"]
        if "instagram" not in clip.published_platforms:
            clip.published_platforms.append("instagram")
        clip.status = "published"

        db.commit()

        return {"status": "success", "post_id": result["post_id"]}

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{clip_id}/youtube")
async def publish_to_youtube_shorts(
    clip_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Publish clip to YouTube Shorts."""
    clip = db.query(Clip).join(Video).filter(
        (Clip.id == clip_id) & (Video.user_id == current_user.id)
    ).first()

    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")

    if not clip.file_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Clip file not available",
        )

    if not current_user.youtube_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="YouTube account not connected",
        )

    try:
        publish_service = PublishService()
        result = publish_service.publish_to_youtube_shorts(
            clip_file_path=clip.file_path,
            title=clip.title,
            caption=clip.caption,
            access_token=current_user.youtube_token,
        )

        clip.youtube_shorts_id = result["post_id"]
        if "youtube_shorts" not in clip.published_platforms:
            clip.published_platforms.append("youtube_shorts")
        clip.status = "published"

        db.commit()

        return {"status": "success", "post_id": result["post_id"]}

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{clip_id}/analytics")
async def get_clip_analytics(
    clip_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get analytics for a published clip."""
    clip = db.query(Clip).join(Video).filter(
        (Clip.id == clip_id) & (Video.user_id == current_user.id)
    ).first()

    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")

    if not clip.analytics:
        return {"message": "No analytics available yet"}

    return clip.analytics
