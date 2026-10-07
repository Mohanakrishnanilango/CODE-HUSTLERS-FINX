from datetime import datetime
import uuid
from sqlalchemy import Column, String, Float, Integer, DateTime
from sqlalchemy.orm import relationship

from app.database.base import Base


class SSSImage(Base):
    __tablename__ = "sss_images"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    filename = Column(String(255), nullable=False)
    file_path = Column(String(512), nullable=False)
    image_width = Column(Integer, nullable=False)
    image_height = Column(Integer, nullable=False)

    # Acoustic and survey metadata
    survey_lat = Column(Float, nullable=True)
    survey_lon = Column(Float, nullable=True)
    heading_deg = Column(Float, nullable=True)
    resolution_m_per_pixel = Column(Float, nullable=True)
    nadir_column = Column(Integer, nullable=True)
    swath_channel = Column(String(32), nullable=True)
    acquisition_timestamp = Column(String(64), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    detections = relationship("Detection", back_populates="image", cascade="all, delete-orphan")
