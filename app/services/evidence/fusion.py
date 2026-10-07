from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.logging import logger
from app.schemas.evidence import CompleteEvidenceSet, EvidenceResult
from app.utils.normalization import clamp_score


class FusionResult(BaseModel):
    """
    Complete audit trail of the evidence fusion calculation.
    Explicitly labels score as 'confidence_score' rather than probability.
    """
    final_confidence: float = Field(..., ge=0.0, le=1.0, description="Fused confidence score between 0.0 and 1.0")
    confidence_percentage: float = Field(..., ge=0.0, le=100.0, description="Confidence expressed as a percentage 0-100%")
    priority: str = Field(..., description="Assigned priority rank: LOW, MEDIUM, or HIGH")
    configured_weights: Dict[str, float] = Field(..., description="Initial engineering weights before redistribution")
    active_weights: Dict[str, float] = Field(..., description="Redistributed weights applied to available modalities")
    modality_breakdown: Dict[str, Dict[str, Any]] = Field(..., description="Audit status and scores for each modality")
    uncalibrated_note: str = Field(
        default="Deterministic multi-criteria evidence fusion score. Not a statistically calibrated probability.",
        description="Scientific qualification note"
    )


def classify_priority(confidence_score: float) -> str:
    """Classifies a confidence score into priority tiers based on configurable thresholds."""
    if confidence_score >= settings.PRIORITY_HIGH_THRESHOLD:
        return "HIGH"
    elif confidence_score >= settings.PRIORITY_MEDIUM_THRESHOLD:
        return "MEDIUM"
    else:
        return "LOW"


def fuse_evidence(
    anomaly_score: float,
    evidence_set: CompleteEvidenceSet,
    custom_weights: Optional[Dict[str, float]] = None,
) -> FusionResult:
    """
    Fuses the external anomaly model score and 5 evidence modalities into an explainable
    confidence score using dynamic weight redistribution for missing modalities.

    Formula:
        W_active = sum(w_i for i in active_modalities)
        w'_i = w_i / W_active
        confidence = sum(w'_i * score_i)
    """
    base_weights = custom_weights or {
        "anomaly": settings.WEIGHT_ANOMALY,
        "shape": settings.WEIGHT_SHAPE,
        "texture": settings.WEIGHT_TEXTURE,
        "shadow": settings.WEIGHT_SHADOW,
        "size": settings.WEIGHT_SIZE,
        "context": settings.WEIGHT_CONTEXT,
    }

    # Collect status and scores from each modality
    modalities: Dict[str, EvidenceResult] = {
        "anomaly": EvidenceResult(
            available=True,
            score=clamp_score(anomaly_score),
            features={"model_anomaly_score": anomaly_score},
            reason=None,
        ),
        "shape": evidence_set.shape,
        "texture": evidence_set.texture,
        "shadow": evidence_set.shadow,
        "size": evidence_set.size,
        "context": evidence_set.context,
    }

    # Determine active vs unavailable modalities
    active_modalities = {}
    modality_breakdown = {}

    for name, res in modalities.items():
        base_w = base_weights.get(name, 0.0)
        status_info = {
            "available": res.available,
            "raw_score": res.score,
            "configured_weight": base_w,
            "reason": res.reason,
        }

        if res.available and res.score is not None:
            active_modalities[name] = (base_w, res.score)
            status_info["status"] = "INCLUDED"
        else:
            status_info["status"] = "EXCLUDED_REDISTRIBUTED"

        modality_breakdown[name] = status_info

    # If no modalities are available (extreme edge case)
    if not active_modalities:
        return FusionResult(
            final_confidence=0.0,
            confidence_percentage=0.0,
            priority="LOW",
            configured_weights=base_weights,
            active_weights={},
            modality_breakdown=modality_breakdown,
        )

    # Dynamic Weight Redistribution
    total_active_weight = sum(w for w, _ in active_modalities.values())
    if total_active_weight <= 0:
        total_active_weight = 1.0

    redistributed_weights = {}
    weighted_sum = 0.0

    for name, (base_w, score) in active_modalities.items():
        redist_w = base_w / total_active_weight
        redistributed_weights[name] = round(redist_w, 4)
        weighted_sum += redist_w * score
        modality_breakdown[name]["effective_weight"] = round(redist_w, 4)
        modality_breakdown[name]["weighted_contribution"] = round(redist_w * score, 4)

    final_confidence = clamp_score(weighted_sum)
    percentage = round(final_confidence * 100.0, 2)
    priority = classify_priority(final_confidence)

    return FusionResult(
        final_confidence=round(final_confidence, 4),
        confidence_percentage=percentage,
        priority=priority,
        configured_weights=base_weights,
        active_weights=redistributed_weights,
        modality_breakdown=modality_breakdown,
    )
