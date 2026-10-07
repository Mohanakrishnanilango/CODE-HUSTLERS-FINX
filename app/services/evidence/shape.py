import math
from typing import Any, Dict, List, Optional, Tuple
import cv2
import numpy as np

from app.core.config import settings
from app.core.logging import logger
from app.schemas.evidence import EvidenceResult
from app.utils.normalization import clamp_score, bell_score, linear_score


def analyze_shape(
    mask: np.ndarray,
    image_shape: Optional[Tuple[int, int]] = None,
    min_area_px: Optional[int] = None,
) -> EvidenceResult:
    """
    Extracts geometric and contour-based shape descriptors from a binary anomaly mask.

    Handles edge cases:
    - Empty masks or all-zero masks
    - Tiny regions smaller than min_area_px
    - Degenerate contours (< 3 vertices)
    - Contours touching image boundaries (partial occlusion/truncation)

    Returns:
        EvidenceResult with available=True/False, raw features, and normalized score.
    """
    if min_area_px is None:
        min_area_px = settings.SHAPE_MIN_CONTOUR_AREA_PX

    if mask is None or mask.size == 0 or np.count_nonzero(mask) == 0:
        return EvidenceResult(
            available=False,
            score=None,
            features={},
            reason="Mask is empty or contains zero positive pixels."
        )

    # Find external contours
    contours, _ = cv2.findContours(
        mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )

    if not contours:
        return EvidenceResult(
            available=False,
            score=None,
            features={},
            reason="No contours found in the provided mask."
        )

    # Select largest contour by area if multiple exist within the mask
    cnt = max(contours, key=cv2.contourArea)
    area = float(cv2.contourArea(cnt))

    if area < min_area_px:
        return EvidenceResult(
            available=False,
            score=None,
            features={"pixel_area": area, "min_area_threshold": min_area_px},
            reason=f"Anomaly region area ({area:.1f} px) is below minimum threshold ({min_area_px} px)."
        )

    if len(cnt) < 3:
        return EvidenceResult(
            available=False,
            score=None,
            features={"pixel_area": area, "num_vertices": len(cnt)},
            reason="Degenerate contour with fewer than 3 vertices."
        )

    # Geometric properties
    perimeter = float(cv2.arcLength(cnt, closed=True))
    x, y, w, h = cv2.boundingRect(cnt)
    aspect_ratio = float(max(w, h)) / float(min(w, h) + 1e-6)
    circularity = (4.0 * math.pi * area) / float(perimeter ** 2 + 1e-6)
    circularity = min(1.0, max(0.0, circularity))

    # Convex hull & solidity
    hull = cv2.convexHull(cnt)
    hull_area = float(cv2.contourArea(hull))
    solidity = area / float(hull_area + 1e-6)
    solidity = min(1.0, max(0.0, solidity))

    extent = area / float(w * h + 1e-6)
    extent = min(1.0, max(0.0, extent))

    # Ellipse fitting for major/minor axes and elongation
    major_axis = float(max(w, h))
    minor_axis = float(min(w, h))
    orientation_deg: Optional[float] = None
    elongation = aspect_ratio

    if len(cnt) >= 5:
        try:
            (cx, cy), (d1, d2), angle = cv2.fitEllipse(cnt)
            major_axis = float(max(d1, d2))
            minor_axis = float(min(d1, d2))
            elongation = major_axis / float(minor_axis + 1e-6)
            orientation_deg = float(angle)
        except cv2.error:
            pass

    # Invariant Hu Moments (log transformed)
    moments = cv2.moments(cnt)
    raw_hu = cv2.HuMoments(moments).flatten()
    log_hu: List[float] = []
    for val in raw_hu:
        if abs(val) > 1e-15:
            log_hu.append(float(-math.copysign(1.0, val) * math.log10(abs(val))))
        else:
            log_hu.append(0.0)

    # Border-touching check
    is_border_touching = False
    if image_shape is not None:
        img_h, img_w = image_shape
        pts = cnt.reshape(-1, 2)
        if (
            np.any(pts[:, 0] <= 0)
            or np.any(pts[:, 0] >= img_w - 1)
            or np.any(pts[:, 1] <= 0)
            or np.any(pts[:, 1] >= img_h - 1)
        ):
            is_border_touching = True

    # Compute Normalized Shape Score [0.0, 1.0]
    # Ghost nets typically exhibit:
    # 1. Non-circular boundary: (1.0 - circularity)
    # 2. Moderate solidity (0.35 to 0.80) due to mesh porosity and ragged outer edges
    # 3. Non-trivial elongation/aspect ratio
    irregularity_score = 1.0 - circularity
    solidity_score = bell_score(solidity, center=0.55, width=0.35)
    elongation_score = linear_score(elongation, min_val=1.0, max_val=5.0)

    # Blend components (weights are descriptive engineering priors)
    raw_score = (
        0.40 * irregularity_score +
        0.35 * solidity_score +
        0.25 * elongation_score
    )

    # Apply boundary truncation uncertainty penalty if touching image border
    if is_border_touching:
        raw_score *= 0.90

    final_score = clamp_score(raw_score)

    features: Dict[str, Any] = {
        "area": round(area, 2),
        "perimeter": round(perimeter, 2),
        "bbox": [int(x), int(y), int(w), int(h)],
        "aspect_ratio": round(aspect_ratio, 3),
        "circularity": round(circularity, 4),
        "solidity": round(solidity, 4),
        "extent": round(extent, 4),
        "elongation": round(elongation, 3),
        "major_axis": round(major_axis, 2),
        "minor_axis": round(minor_axis, 2),
        "orientation_deg": round(orientation_deg, 2) if orientation_deg is not None else None,
        "is_border_touching": is_border_touching,
        "hu_moments": [round(h_val, 4) for h_val in log_hu],
    }

    return EvidenceResult(
        available=True,
        score=round(final_score, 4),
        features=features,
        reason=None if not is_border_touching else "Anomaly touches image margin; shape may be partially truncated."
    )
