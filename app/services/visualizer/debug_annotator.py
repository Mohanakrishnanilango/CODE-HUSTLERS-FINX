import os
from typing import Any, Dict, Optional, Tuple
import cv2
import numpy as np

from app.core.config import settings
from app.core.logging import logger
from app.schemas.evidence import CompleteEvidenceSet
from app.services.evidence.fusion import FusionResult


def generate_annotated_debug_image(
    original_image: np.ndarray,
    anomaly_mask: np.ndarray,
    bbox: Tuple[int, int, int, int],
    shadow_mask: Optional[np.ndarray],
    fusion_result: FusionResult,
    region_id: str,
    output_filename: Optional[str] = None,
) -> str:
    """
    Renders a multi-layer diagnostic HUD overlay on the original SSS image.

    Color coding:
    - Anomaly Bounding Box: Yellow (0, 255, 255)
    - Anomaly Contour: Cyan (255, 255, 0)
    - Acoustic Shadow: Red / Crimson (0, 0, 220)
    - Seafloor Context Ring: Lime Green (0, 255, 0)
    - HUD Header: Dark banner with ID, Anomaly Score, Confidence, and Priority badge

    Saves to storage/debug_outputs/ and returns the relative/absolute file path.
    """
    os.makedirs(settings.DEBUG_OUTPUT_DIR, exist_ok=True)

    img_h, img_w = original_image.shape[:2]

    # Convert grayscale SSS to BGR color canvas
    if original_image.ndim == 2:
        canvas = cv2.cvtColor(original_image, cv2.COLOR_GRAY2BGR)
    else:
        canvas = original_image.copy()

    x, y, w, h = bbox

    # 1. Overlay Seafloor Context Annulus (Dilation of anomaly minus anomaly)
    kernel_context = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (51, 51))
    dilated_mask = cv2.dilate(anomaly_mask, kernel_context)
    context_ring = cv2.bitwise_and(dilated_mask, cv2.bitwise_not(anomaly_mask))
    if shadow_mask is not None:
        context_ring = cv2.bitwise_and(context_ring, cv2.bitwise_not(shadow_mask))

    ring_contours, _ = cv2.findContours(context_ring, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(canvas, ring_contours, -1, (0, 180, 0), 1)  # Green ring

    # 2. Overlay Acoustic Shadow (Translucent Red)
    if shadow_mask is not None and np.count_nonzero(shadow_mask) > 0:
        shadow_overlay = canvas.copy()
        shadow_overlay[shadow_mask > 0] = [0, 0, 220]  # Crimson red
        cv2.addWeighted(shadow_overlay, 0.45, canvas, 0.55, 0, canvas)
        # Draw shadow boundary
        s_contours, _ = cv2.findContours(shadow_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(canvas, s_contours, -1, (0, 0, 255), 2)

    # 3. Overlay Anomaly Highlight (Translucent Cyan Fill + Solid Cyan Contour)
    anomaly_overlay = canvas.copy()
    anomaly_overlay[anomaly_mask > 0] = [230, 210, 0]  # Light cyan/blue
    cv2.addWeighted(anomaly_overlay, 0.40, canvas, 0.60, 0, canvas)

    a_contours, _ = cv2.findContours(anomaly_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(canvas, a_contours, -1, (255, 255, 0), 2)  # Cyan boundary

    # 4. Draw Anomaly Bounding Box (Yellow)
    cv2.rectangle(canvas, (x, y), (x + w, y + h), (0, 230, 255), 2)

    # 5. Draw Top HUD Diagnostic Banner
    banner_height = 42
    banner = np.zeros((banner_height, img_w, 3), dtype=np.uint8)
    banner[:] = (30, 30, 30)  # Dark gray background

    # Priority badge color
    if fusion_result.priority == "HIGH":
        badge_color = (0, 0, 255)     # Red
    elif fusion_result.priority == "MEDIUM":
        badge_color = (0, 165, 255)   # Orange
    else:
        badge_color = (0, 200, 0)     # Green

    # Text overlay
    title_text = f"ID: {region_id} | Conf: {fusion_result.confidence_percentage:.1f}% | Priority: {fusion_result.priority}"
    cv2.putText(banner, title_text, (12, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.60, (255, 255, 255), 1, cv2.LINE_AA)

    # Shadow status indicator
    shadow_detected = fusion_result.modality_breakdown.get("shadow", {}).get("raw_score", 0.0)
    shadow_status = "SHADOW: DETECTED" if (shadow_detected and shadow_detected > 0) else "SHADOW: NONE"
    cv2.putText(banner, shadow_status, (max(12, img_w - 220), 26), cv2.FONT_HERSHEY_SIMPLEX, 0.50, (200, 200, 200), 1, cv2.LINE_AA)

    # Prepend banner to top of canvas
    final_debug_img = np.vstack([banner, canvas])

    # Save to file
    if output_filename is None:
        output_filename = f"{region_id}_debug.png"

    output_path = os.path.join(settings.DEBUG_OUTPUT_DIR, output_filename)
    cv2.imwrite(output_path, final_debug_img)
    logger.info("Saved visual debug image to %s", output_path)

    return output_path
