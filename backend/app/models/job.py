from sqlalchemy import Column, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from .base import Base
import uuid


class Job(Base):
    __tablename__ = "jobs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    video_id = Column(String, ForeignKey("videos.id"))

    # Task type: download, analyze_audio, analyze_video, analyze_content, generate_clips
    task_type = Column(String, index=True)

    # Status: pending, processing, completed, failed
    status = Column(String, default="pending", index=True)

    celery_task_id = Column(String, nullable=True, unique=True)
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    video = relationship("Video", back_populates="jobs")
