from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class VideoCreate(BaseModel):
    youtube_url: str
    # Spans worth clipping, [[start, end], ...] in seconds. Empty or absent
    # means the whole video, which is how every upload worked before.
    ranges: Optional[List[List[float]]] = None


class VideoReprocess(BaseModel):
    """Re-run analysis on a video already downloaded, with new spans."""

    ranges: Optional[List[List[float]]] = None


class VideoUpdate(BaseModel):
    title: Optional[str] = None
    video_metadata: Optional[dict] = None


class VideoResponse(BaseModel):
    id: str
    youtube_url: str
    title: Optional[str] = None
    channel_name: Optional[str] = None
    duration_seconds: Optional[int] = None
    status: str
    clip_ranges: Optional[List[List[float]]] = None
    processing_progress: float
    thumbnail_url: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    error_message: Optional[str] = None

    class Config:
        from_attributes = True


class VideoListResponse(BaseModel):
    videos: List[VideoResponse]
    total: int
