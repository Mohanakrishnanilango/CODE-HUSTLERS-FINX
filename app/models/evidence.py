from datetime import datetime
import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship

from app.database.base import Base


class DetectionEvidence(Base):
    __tablename__ = "detection_evidences"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    detection_id = Column(String(36), ForeignKey("detections.id", ondelete="CASCADE"), nullable=False, unique=True)

    # Detailed raw features
    shape_features = Column(JSON, nullable=False)
    texture_features = Column(JSON, nullable=False)
    shadow_features = Column(JSON, nullable=False)
    size_features = Column(JSON, nullable=False)
    context_features = Column(JSON, nullable=False)

    # Normalized evidence scores & fusion breakdown
    normalized_scores = Column(JSON, nullable=False)
    fusion_audit = Column(JSON, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    detection = relationship("Detection", back_populates="evidence")
