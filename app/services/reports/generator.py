from datetime import datetime
import json
import os
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.schemas.evidence import CompleteEvidenceSet
from app.services.evidence.fusion import FusionResult
from app.services.geolocation.calculator import GeolocationResult


class ReportGenerator:
    """Generates structured audit reports (JSON and Markdown) for acoustic detections."""

    @staticmethod
    def generate_json_report(
        detection_id: str,
        image_name: str,
        anomaly_score: float,
        evidence_set: CompleteEvidenceSet,
        fusion_result: FusionResult,
        geolocation: GeolocationResult,
        debug_image_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Builds a comprehensive JSON audit report."""
        return {
            "detection_id": detection_id,
            "image_reference": image_name,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "anomaly_score": round(anomaly_score, 4),
            "final_confidence": fusion_result.final_confidence,
            "confidence_percentage": fusion_result.confidence_percentage,
            "priority": fusion_result.priority,
            "geolocation": {
                "available": geolocation.available,
                "latitude": geolocation.latitude,
                "longitude": geolocation.longitude,
                "reason": geolocation.reason,
                "coordinate_assumptions": geolocation.coordinate_assumptions,
            },
            "evidence": {
                "shape": evidence_set.shape.model_dump(),
                "texture": evidence_set.texture.model_dump(),
                "shadow": evidence_set.shadow.model_dump(),
                "size": evidence_set.size.model_dump(),
                "context": evidence_set.context.model_dump(),
            },
            "fusion_audit": {
                "configured_weights": fusion_result.configured_weights,
                "active_weights": fusion_result.active_weights,
                "modality_breakdown": fusion_result.modality_breakdown,
                "qualification_note": fusion_result.uncalibrated_note,
            },
            "debug_visualization": debug_image_path,
        }

    @staticmethod
    def generate_markdown_report(report_data: Dict[str, Any]) -> str:
        """Renders report data as formatted GitHub Markdown."""
        d_id = report_data["detection_id"]
        conf = report_data["confidence_percentage"]
        prio = report_data["priority"]
        geo = report_data["geolocation"]
        ev = report_data["evidence"]
        f_audit = report_data["fusion_audit"]

        geo_str = (
            f"**Latitude:** {geo['latitude']:.6f}° N, **Longitude:** {geo['longitude']:.6f}° E (WGS84)"
            if geo["available"]
            else f"**Unavailable** ({geo.get('reason', 'Metadata missing')})"
        )

        md = f"""# SSS Ghost Net Detection Audit Report

**Detection ID:** `{d_id}`  
**Image Reference:** `{report_data['image_reference']}`  
**Timestamp:** `{report_data['timestamp']}`  
**Assigned Priority:** **{prio}**  
**Final Confidence Score:** **{conf:.1f}%** (`{report_data['final_confidence']:.4f}`)  
**Geolocation:** {geo_str}  

> [!NOTE]
> {f_audit.get('qualification_note', 'Deterministic multi-criteria evidence fusion score. Not a calibrated probability.')}

---

## 1. Multi-Modal Evidence Breakdown

| Modality | Status | Normalized Score | Effective Weight | Reason / Diagnostics |
| :--- | :--- | :--- | :--- | :--- |
| **Model Anomaly** | INCLUDED | `{report_data['anomaly_score']:.4f}` | `{f_audit['active_weights'].get('anomaly', 0.0):.3f}` | External candidate highlight detection |
| **Shape** | {'AVAILABLE' if ev['shape']['available'] else 'UNAVAILABLE'} | `{ev['shape']['score']}` | `{f_audit['active_weights'].get('shape', 0.0):.3f}` | {ev['shape'].get('reason') or 'OK'} |
| **Texture (GLCM)** | {'AVAILABLE' if ev['texture']['available'] else 'UNAVAILABLE'} | `{ev['texture']['score']}` | `{f_audit['active_weights'].get('texture', 0.0):.3f}` | {ev['texture'].get('reason') or 'OK'} |
| **Acoustic Shadow** | {'AVAILABLE' if ev['shadow']['available'] else 'UNAVAILABLE'} | `{ev['shadow']['score']}` | `{f_audit['active_weights'].get('shadow', 0.0):.3f}` | {ev['shadow'].get('reason') or 'OK'} |
| **Size & Extent** | {'AVAILABLE' if ev['size']['available'] else 'UNAVAILABLE'} | `{ev['size']['score']}` | `{f_audit['active_weights'].get('size', 0.0):.3f}` | {ev['size'].get('reason') or 'OK'} |
| **Seafloor Context** | {'AVAILABLE' if ev['context']['available'] else 'UNAVAILABLE'} | `{ev['context']['score']}` | `{f_audit['active_weights'].get('context', 0.0):.3f}` | {ev['context'].get('reason') or 'OK'} |

---

## 2. Key Physical Measurements

* **Pixel Area:** {ev['size']['features'].get('pixel_area', 'N/A')} px
* **Physical Extent:** {ev['size']['features'].get('extent_meters', 'N/A')} m
* **Physical Area:** {ev['size']['features'].get('area_sq_meters', 'N/A')} m²
* **Shape Circularity:** {ev['shape']['features'].get('circularity', 'N/A')}
* **Shape Solidity:** {ev['shape']['features'].get('solidity', 'N/A')}
* **Acoustic Shadow Detected:** {ev['shadow']['features'].get('shadow_detected', False)}
* **Shadow / Highlight Area Ratio:** {ev['shadow']['features'].get('shadow_to_anomaly_ratio', 'N/A')}
* **Seafloor Weber Contrast:** {ev['context']['features'].get('weber_contrast', 'N/A')}
* **Seafloor Background Uniformity:** {ev['context']['features'].get('background_uniformity', 'N/A')}

---

## 3. Visual Verification Artifact
`{report_data.get('debug_visualization') or 'N/A'}`
"""
        return md
