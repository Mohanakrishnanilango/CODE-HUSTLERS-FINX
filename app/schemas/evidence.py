from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class EvidenceResult(BaseModel):
    """
    Unified container for any evidence extraction module.
    Encapsulates availability, normalized score, raw physical/mathematical features,
    and explanatory reasons for absence/degradation.
    """
    available: bool = Field(
        ...,
        description="Whether this evidence modality was successfully calculated"
    )
    score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Normalized evidence score between 0.0 and 1.0 (None if unavailable)"
    )
    features: Dict[str, Any] = Field(
        default_factory=dict,
        description="Raw physical, geometric, or statistical measurements"
    )
    reason: Optional[str] = Field(
        default=None,
        description="Explanation when evidence calculation failed or was skipped"
    )


class CompleteEvidenceSet(BaseModel):
    """
    Container aggregating all 5 evidence modalities for a single anomaly region.
    """
    shape: EvidenceResult
    texture: EvidenceResult
    shadow: EvidenceResult
    size: EvidenceResult
    context: EvidenceResult
