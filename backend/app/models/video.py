from sqlalchemy import Column, String, Integer, Float, DateTime, JSON, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from .base import Base
import uuid


class Video(Base):
    __tablename__ = "videos"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"))

    youtube_url = Column(String)
    youtube_video_id = Column(String, index=True)
    title = Column(String)
    channel_name = Column(String)
    thumbnail_url = Column(String, nullable=True)

    duration_seconds = Column(Integer)
    file_path = Column(String, nullable=True)

    # Status: pending, downloading, processing, completed, error
    status = Column(String, default="pending", index=True)

    # NOTE: named video_metadata (not `metadata`) because SQLAlchemy's
    # declarative Base reserves the `metadata` attribute name.
    video_metadata = Column(JSON, nullable=True)  # resolution, fps, codec, ai scores, etc
    error_message = Column(String, nullable=True)

    # Processing progress
    processing_progress = Column(Float, default=0)  # 0-100

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="videos")
    clips = relationship("Clip", back_populates="video", cascade="all, delete-orphan")
    jobs = relationship("Job", back_populates="video", cascade="all, delete-orphan")
