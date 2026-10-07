from datetime import datetime
import uuid
from sqlalchemy import Column, String, Float, Integer, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.core.config import settings
from app.database.base import Base

# Dynamic spatial column setup: PostGIS for PostgreSQL, String/WKT for SQLite unit tests
if settings.USE_SQLITE_TEST or settings.DATABASE_URL.startswith("sqlite"):
    GeomType = String
else:
    try:
        from geoalchemy2 import Geometry
        GeomType = Geometry(geometry_type="POINT", srid=4326, spatial_index=True)
    except ImportError:
        GeomType = String


class Detection(Base):
    __tablename__ = "detections"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    image_id = Column(String(36), ForeignKey("sss_images.id", ondelete="CASCADE"), nullable=False)
    region_id = Column(String(64), nullable=False)

    # Bounding rectangle
    bbox_x = Column(Integer, nullable=False)
    bbox_y = Column(Integer, nullable=False)
    bbox_w = Column(Integer, nullable=False)
    bbox_h = Column(Integer, nullable=False)

    # Fused results
    anomaly_score = Column(Float, nullable=False)
    final_confidence = Column(Float, nullable=False)
    confidence_percentage = Column(Float, nullable=False)
    priority = Column(String(16), nullable=False)  # LOW, MEDIUM, HIGH

    # Geographic coordinates (nullable if metadata was insufficient)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    geom = Column(GeomType, nullable=True)

    # Debug image artifact location
    debug_image_path = Column(String(512), nullable=True)
    processing_status = Column(String(32), default="COMPLETED", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    image = relationship("SSSImage", back_populates="detections")
    evidence = relationship("DetectionEvidence", back_populates="detection", uselist=False, cascade="all, delete-orphan")
