from typing import Any, Dict, Optional, Tuple
import cv2
import numpy as np

from app.core.config import settings
from app.core.logging import logger
from app.schemas.evidence import EvidenceResult
from app.schemas.survey import SurveyMetadata
from app.utils.normalization import clamp_score, linear_score, sigmoid_score, bell_score


def determine_shadow_direction(
    bbox: Tuple[int, int, int, int],
    image_shape: Tuple[int, int],
    metadata: Optional[SurveyMetadata] = None,
    mode: Optional[str] = None,
) -> Tuple[Optional[str], Optional[str]]:
    """
    Determines acoustic propagation direction based on sonar geometry metadata.

    Returns:
        (direction, reason):
        direction: 'right', 'left', 'down', 'up', or None
        reason: diagnostic explanation if direction could not be determined
    """
    if mode is None:
        mode = settings.SHADOW_DIRECTION_MODE

    x, y, w, h = bbox
    img_h, img_w = image_shape
    centroid_x = x + w / 2.0

    if mode == "starboard":
        return "right", None
    elif mode == "port":
        return "left", None

    if mode in ("metadata_based", "away_from_nadir"):
        # Check swath channel
        if metadata and metadata.swath_channel:
            ch = metadata.swath_channel.lower()
            if ch == "starboard":
                return "right", None
            elif ch == "port":
                return "left", None

        # Check nadir column
        nadir_col = metadata.nadir_column if (metadata and metadata.nadir_column is not None) else None
        if nadir_col is None and mode == "away_from_nadir":
            # Default assumption for full swath: center column is nadir
            nadir_col = img_w // 2

        if nadir_col is not None:
            if centroid_x >= nadir_col:
                return "right", None  # Starboard of track: acoustic rays travel left-to-right
            else:
                return "left", None   # Port of track: acoustic rays travel right-to-left

        if mode == "metadata_based":
            return (
                None,
                "Insufficient sonar geometry metadata (nadir_column or swath_channel) "
                "to determine physical acoustic shadow propagation direction."
            )

    if mode == "adaptive":
        # Fallback to bilateral search (evaluates both left and right for candidate shadow)
        return "adaptive", None

    return None, f"Unknown shadow direction mode: {mode}"


def analyze_shadow(
    image: np.ndarray,
    anomaly_mask: np.ndarray,
    bbox: Tuple[int, int, int, int],
    metadata: Optional[SurveyMetadata] = None,
    direction_mode: Optional[str] = None,
) -> Tuple[EvidenceResult, Optional[np.ndarray]]:
    """
    Acoustic sonar shadow analysis based on physical sonar geometry.

    Returns:
        (EvidenceResult, shadow_mask)
    """
    if anomaly_mask is None or np.count_nonzero(anomaly_mask) == 0:
        return (
            EvidenceResult(
                available=False,
                score=None,
                features={},
                reason="Anomaly mask is empty; cannot construct shadow search corridor."
            ),
            None
        )

    img_h, img_w = image.shape[:2]
    x, y, w, h = bbox
    anomaly_area = float(np.count_nonzero(anomaly_mask))

    # 1. Determine acoustic propagation direction
    direction, dir_reason = determine_shadow_direction(
        bbox=bbox,
        image_shape=(img_h, img_w),
        metadata=metadata,
        mode=direction_mode,
    )

    if direction is None:
        return (
            EvidenceResult(
                available=False,
                score=None,
                features={"shadow_detected": False},
                reason=dir_reason
            ),
            None
        )

    # 2. Construct Search Corridor
    # An acoustic shadow forms immediately behind the highlight along the acoustic propagation ray
    corridor_mult = 2.0
    search_w = int(max(w * corridor_mult, 30))
    search_h = int(max(h * 1.4, 20))

    directions_to_try = [direction] if direction != "adaptive" else ["right", "left"]
    best_candidate: Optional[Dict[str, Any]] = None
    best_shadow_mask: Optional[np.ndarray] = None

    for d in directions_to_try:
        if d == "right":
            # Starboard: shadow is to the right of anomaly
            sx1 = min(img_w, x + w)
            sx2 = min(img_w, x + w + search_w)
            sy1 = max(0, y - int(h * 0.2))
            sy2 = min(img_h, y + h + int(h * 0.2))
        else:
            # Port: shadow is to the left of anomaly
            sx1 = max(0, x - search_w)
            sx2 = max(0, x)
            sy1 = max(0, y - int(h * 0.2))
            sy2 = min(img_h, y + h + int(h * 0.2))

        if sx2 <= sx1 or sy2 <= sy1:
            continue

        corridor_roi = image[sy1:sy2, sx1:sx2]
        if corridor_roi.size < 16:
            continue

        # 3. Estimate Local Seabed Baseline in adjacent unoccluded zone
        # Sample an unoccluded strip above/below the corridor
        bg_y1 = max(0, sy1 - 20)
        bg_y2 = sy1
        if bg_y2 - bg_y1 >= 5:
            bg_strip = image[bg_y1:bg_y2, sx1:sx2]
            bg_mean = float(np.mean(bg_strip))
            bg_std = float(np.std(bg_strip))
        else:
            bg_mean = float(np.mean(corridor_roi))
            bg_std = float(np.std(corridor_roi))

        # 4. Adaptive Thresholding
        # Acoustic shadow represents genuine sound attenuation approaching receiver noise floor
        p15 = float(np.percentile(corridor_roi, settings.SHADOW_PERCENTILE_CUTOFF))
        adaptive_cutoff = bg_mean - settings.SHADOW_SIGMA_FACTOR * bg_std
        threshold_val = max(5.0, min(p15, adaptive_cutoff, float(settings.SHADOW_ABSOLUTE_MAX_INTENSITY)))

        # Binary candidate shadow in corridor
        raw_shadow = (corridor_roi <= threshold_val).astype(np.uint8) * 255

        # 5. Morphological Filtering
        kernel3 = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        # Open to eliminate single-pixel speckle noise dropouts
        opened = cv2.morphologyEx(raw_shadow, cv2.MORPH_OPEN, kernel3)
        # Close to unite contiguous acoustic shadow fragments
        cleaned_corridor = cv2.morphologyEx(opened, cv2.MORPH_CLOSE, kernel3)

        # 6. Connected Component Analysis & Adjacency
        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(
            cleaned_corridor, connectivity=8
        )

        full_mask_candidate = np.zeros((img_h, img_w), dtype=np.uint8)
        selected_area = 0
        comp_intensities = []

        for lbl in range(1, num_labels):
            comp_w = stats[lbl, cv2.CC_STAT_WIDTH]
            comp_h = stats[lbl, cv2.CC_STAT_HEIGHT]
            comp_area = stats[lbl, cv2.CC_STAT_AREA]

            if comp_area < settings.SHADOW_MIN_AREA_PX:
                continue

            # Check adjacency to anomaly boundary
            # Map component back to full image coordinates
            comp_cx = sx1 + centroids[lbl][0]
            comp_cy = sy1 + centroids[lbl][1]

            # Minimum distance between anomaly bbox and component
            if d == "right":
                dist = max(0.0, (sx1 + stats[lbl, cv2.CC_STAT_LEFT]) - (x + w))
            else:
                dist = max(0.0, x - (sx1 + stats[lbl, cv2.CC_STAT_LEFT] + comp_w))

            if dist <= settings.SHADOW_ADJACENCY_MAX_DISTANCE_PX:
                # Valid adjacent acoustic shadow component
                c_mask = (labels == lbl).astype(np.uint8) * 255
                full_mask_candidate[sy1:sy2, sx1:sx2] = cv2.bitwise_or(
                    full_mask_candidate[sy1:sy2, sx1:sx2], c_mask
                )
                selected_area += comp_area
                comp_pixels = corridor_roi[labels == lbl]
                comp_intensities.extend(comp_pixels.tolist())

        if selected_area >= settings.SHADOW_MIN_AREA_PX:
            mean_intensity = float(np.mean(comp_intensities)) if comp_intensities else 0.0
            area_ratio = float(selected_area) / float(anomaly_area + 1e-6)

            # Score confidence based on darkness, size plausibility, and proximity
            darkness_score = linear_score(mean_intensity, min_val=0.0, max_val=40.0, invert=True)
            ratio_score = bell_score(area_ratio, center=1.2, width=1.5)
            cand_score = clamp_score(0.60 * darkness_score + 0.40 * ratio_score)

            if best_candidate is None or cand_score > best_candidate["score"]:
                best_candidate = {
                    "direction": d,
                    "shadow_detected": True,
                    "shadow_area": int(selected_area),
                    "shadow_mean_intensity": round(mean_intensity, 2),
                    "shadow_to_anomaly_ratio": round(area_ratio, 3),
                    "distance_to_anomaly_px": 0.0,
                    "threshold_applied": round(threshold_val, 2),
                    "score": round(cand_score, 4),
                }
                best_shadow_mask = full_mask_candidate

    if best_candidate is not None:
        return (
            EvidenceResult(
                available=True,
                score=best_candidate["score"],
                features=best_candidate,
                reason=None,
            ),
            best_shadow_mask
        )

    # No acoustic shadow detected
    return (
        EvidenceResult(
            available=True,
            score=0.0,
            features={
                "direction": direction,
                "shadow_detected": False,
                "shadow_area": 0,
                "shadow_to_anomaly_ratio": 0.0,
                "reason": "No contiguous acoustic dropout component met adjacency criteria in the search corridor."
            },
            reason="No acoustic shadow detected adjacent to anomaly."
        ),
        np.zeros((img_h, img_w), dtype=np.uint8)
    )
