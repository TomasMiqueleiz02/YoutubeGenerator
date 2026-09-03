from sqlalchemy import Column, String, Float, DateTime, JSON, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from .base import Base
import uuid


class Clip(Base):
    __tablename__ = "clips"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    video_id = Column(String, ForeignKey("videos.id"))

    start_time = Column(Float)  # seconds
    end_time = Column(Float)    # seconds
    duration = Column(Float)    # end_time - start_time

    virality_score = Column(Float)  # 0-100
    audio_score = Column(Float)     # audio component
    video_score = Column(Float)     # video component
    content_score = Column(Float)   # content component

    title = Column(String, nullable=True)
    caption = Column(Text, nullable=True)

    file_path = Column(String, nullable=True)
    thumbnail_path = Column(String, nullable=True)

    # Status: generated, edited, published, scheduled
    status = Column(String, default="generated", index=True)

    # Published platforms: ['tiktok', 'instagram', 'youtube_shorts']
    published_platforms = Column(JSON, default=list)

    # Platform specific IDs
    tiktok_post_id = Column(String, nullable=True)
    instagram_post_id = Column(String, nullable=True)
    youtube_shorts_id = Column(String, nullable=True)

    # Analytics
    analytics = Column(JSON, nullable=True)  # views, likes, shares, etc

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    published_at = Column(DateTime, nullable=True)

    # Relationships
    video = relationship("Video", back_populates="clips")
