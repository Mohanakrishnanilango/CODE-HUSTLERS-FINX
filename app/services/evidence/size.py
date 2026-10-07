import math
from typing import Any, Dict, Optional, Tuple
import cv2
import numpy as np

from app.core.config import settings
from app.core.logging import logger
from app.schemas.evidence import EvidenceResult
from app.schemas.survey import SurveyMetadata
from app.utils.normalization import clamp_score, sigmoid_score


def analyze_size(
    mask: np.ndarray,
    bbox: Tuple[int, int, int, int],
    metadata: Optional[SurveyMetadata] = None,
    require_physical: bool = True,
) -> EvidenceResult:
    """
    Extracts descriptive size and extent features from an anomaly mask.

    Computes:
    - Pixel measurements: area, bbox width/height, extent, major/minor axis lengths.
    - Physical measurements (meters, m^2) if spatial resolution (m/pixel) is available.

    If resolution is missing and require_physical is True, marks evidence as unavailable
    to trigger dynamic fusion weight redistribution without penalty.
    """
    if mask is None or np.count_nonzero(mask) == 0:
        return EvidenceResult(
            available=False,
            score=None,
            features={"physical_size_calculated": False},
            reason="Empty mask; cannot compute size or extent."
        )

    x, y, w, h = bbox
    pixel_area = float(np.count_nonzero(mask))
    extent = pixel_area / float(w * h + 1e-6)

    # Major and minor axes from contour
    major_axis_px = float(max(w, h))
    minor_axis_px = float(min(w, h))

    contours, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if contours:
        cnt = max(contours, key=cv2.contourArea)
        if len(cnt) >= 5:
            try:
                _, (d1, d2), _ = cv2.fitEllipse(cnt)
                major_axis_px = float(max(d1, d2))
                minor_axis_px = float(min(d1, d2))
            except cv2.error:
                pass

    resolution = metadata.resolution_m_per_pixel if (metadata and metadata.resolution_m_per_pixel) else None

    features: Dict[str, Any] = {
        "pixel_area": int(pixel_area),
        "bbox_width_px": int(w),
        "bbox_height_px": int(h),
        "extent": round(extent, 4),
        "major_axis_px": round(major_axis_px, 2),
        "minor_axis_px": round(minor_axis_px, 2),
        "resolution_m_per_pixel": resolution,
    }

    if resolution is not None and resolution > 0:
        width_m = float(w) * resolution
        height_m = float(h) * resolution
        area_m2 = pixel_area * (resolution ** 2)
        extent_m = float(max(width_m, height_m))
        major_axis_m = major_axis_px * resolution
        minor_axis_m = minor_axis_px * resolution

        features.update({
            "physical_size_calculated": True,
            "width_meters": round(width_m, 2),
            "height_meters": round(height_m, 2),
            "area_sq_meters": round(area_m2, 2),
            "extent_meters": round(extent_m, 2),
            "major_axis_meters": round(major_axis_m, 2),
            "minor_axis_meters": round(minor_axis_m, 2),
        })

        # Configurable descriptive score (non-punitive, tuneable with validation data)
        # Filters out microscopic sensor speckle (< 0.5m) and massive geologic ridges (> 150m)
        lower_bound_score = sigmoid_score(extent_m, center=1.0, slope=2.0)
        upper_bound_score = sigmoid_score(extent_m, center=120.0, slope=-0.05)
        metric_score = clamp_score(lower_bound_score * upper_bound_score)

        return EvidenceResult(
            available=True,
            score=round(metric_score, 4),
            features=features,
            reason=None,
        )
    else:
        # Resolution unavailable
        features.update({
            "physical_size_calculated": False,
            "width_meters": None,
            "height_meters": None,
            "area_sq_meters": None,
            "extent_meters": None,
            "major_axis_meters": None,
            "minor_axis_meters": None,
        })

        if require_physical:
            return EvidenceResult(
                available=False,
                score=None,
                features=features,
                reason="Spatial resolution metadata (m/pixel) unavailable; physical metric size could not be computed."
            )
        else:
            # Fallback to pixel descriptive score if explicitly requested
            px_score = clamp_score(sigmoid_score(pixel_area, center=50.0, slope=0.05))
            return EvidenceResult(
                available=True,
                score=round(px_score, 4),
                features=features,
                reason="Physical resolution missing; descriptive score estimated from pixel dimensions only."
            )
