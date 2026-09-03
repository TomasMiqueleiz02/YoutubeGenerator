from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class ClipCreate(BaseModel):
    video_id: str
    start_time: float
    end_time: float
    title: Optional[str] = None
    caption: Optional[str] = None


class ClipUpdate(BaseModel):
    title: Optional[str] = None
    caption: Optional[str] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None


class ClipResponse(BaseModel):
    id: str
    video_id: str
    start_time: float
    end_time: float
    duration: float
    virality_score: Optional[float] = None
    audio_score: Optional[float] = None
    video_score: Optional[float] = None
    content_score: Optional[float] = None
    title: Optional[str] = None
    caption: Optional[str] = None
    status: str
    published_platforms: List[str] = []
    thumbnail_path: Optional[str] = None
    created_at: datetime
    published_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ClipListResponse(BaseModel):
    clips: List[ClipResponse]
    total: int
