from pydantic import BaseModel, HttpUrl
from typing import Optional, List
from datetime import datetime


class VideoCreate(BaseModel):
    youtube_url: HttpUrl


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
