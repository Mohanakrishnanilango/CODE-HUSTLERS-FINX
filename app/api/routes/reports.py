from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.detection import Detection
from app.models.evidence import DetectionEvidence
from app.models.survey import SSSImage
from app.schemas.evidence import CompleteEvidenceSet, EvidenceResult
from app.services.evidence.fusion import FusionResult
from app.services.geolocation.calculator import GeolocationResult
from app.services.reports.generator import ReportGenerator

router = APIRouter(prefix="/detections", tags=["Reports"])


@router.get("/{detection_id}/report")
def get_detection_report(
    detection_id: str,
    format: str = Query("json", description="Output format: 'json' or 'markdown'"),
    db: Session = Depends(get_db),
):
    """
    Generates a comprehensive audit report for a specific detection.
    Supports structured JSON format and human-readable Markdown format.
    """
    det = db.query(Detection).filter(Detection.id == detection_id).first()
    if not det:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Detection not found")

    ev = db.query(DetectionEvidence).filter(DetectionEvidence.detection_id == detection_id).first()
    if not ev:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidence not found")

    img = db.query(SSSImage).filter(SSSImage.id == det.image_id).first()
    image_name = img.filename if img else "unknown_sss_image"

    # Reconstruct Evidence Set
    scores = ev.normalized_scores or {}

    def make_res(name: str, features: dict) -> EvidenceResult:
        sc = scores.get(name)
        return EvidenceResult(available=sc is not None, score=sc, features=features or {})

    evidence_set = CompleteEvidenceSet(
        shape=make_res("shape", ev.shape_features),
        texture=make_res("texture", ev.texture_features),
        shadow=make_res("shadow", ev.shadow_features),
        size=make_res("size", ev.size_features),
        context=make_res("context", ev.context_features),
    )

    fusion_audit = ev.fusion_audit or {}
    fusion_result = FusionResult(
        final_confidence=det.final_confidence,
        confidence_percentage=det.confidence_percentage,
        priority=det.priority,
        configured_weights=fusion_audit.get("configured_weights", {}),
        active_weights=fusion_audit.get("active_weights", {}),
        modality_breakdown=fusion_audit.get("modality_breakdown", {}),
    )

    geo_result = GeolocationResult(
        available=det.latitude is not None and det.longitude is not None,
        latitude=det.latitude,
        longitude=det.longitude,
        reason=None if (det.latitude is not None) else "Survey geolocation metadata missing",
    )

    json_report = ReportGenerator.generate_json_report(
        detection_id=det.id,
        image_name=image_name,
        anomaly_score=det.anomaly_score,
        evidence_set=evidence_set,
        fusion_result=fusion_result,
        geolocation=geo_result,
        debug_image_path=det.debug_image_path,
    )

    if format.lower() == "markdown":
        md_text = ReportGenerator.generate_markdown_report(json_report)
        return Response(content=md_text, media_type="text/markdown")

    return json_report
