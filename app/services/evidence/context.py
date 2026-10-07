from typing import Any, Dict, Optional, Tuple
import cv2
import numpy as np
from scipy.stats import wasserstein_distance

from app.core.config import settings
from app.core.logging import logger
from app.schemas.evidence import EvidenceResult
from app.utils.image_processing import create_annular_context_mask
from app.utils.normalization import clamp_score, linear_score, sigmoid_score


def analyze_seafloor_context(
    image: np.ndarray,
    anomaly_mask: np.ndarray,
    shadow_mask: Optional[np.ndarray] = None,
    dilation_radius_px: Optional[int] = None,
) -> EvidenceResult:
    """
    Evaluates acoustic contrast and statistical divergence between the anomaly candidate
    and the immediately surrounding ambient seafloor.

    Uses an annular background ROI that excludes the anomaly itself and any acoustic shadow.
    """
    if dilation_radius_px is None:
        dilation_radius_px = settings.CONTEXT_DILATION_RADIUS_PX

    anomaly_pixels = image[anomaly_mask > 0]
    if len(anomaly_pixels) < settings.SHAPE_MIN_CONTOUR_AREA_PX:
        return EvidenceResult(
            available=False,
            score=None,
            features={},
            reason="Insufficient pixels in anomaly mask to evaluate seafloor context."
        )

    # Construct clean annular background mask
    bg_mask = create_annular_context_mask(
        mask=anomaly_mask,
        shadow_mask=shadow_mask,
        dilation_radius=dilation_radius_px,
    )

    bg_pixels = image[bg_mask > 0]
    if len(bg_pixels) < settings.CONTEXT_MIN_BACKGROUND_PIXELS:
        return EvidenceResult(
            available=False,
            score=None,
            features={"valid_background_pixels": len(bg_pixels)},
            reason=f"Insufficient background seafloor pixels (< {settings.CONTEXT_MIN_BACKGROUND_PIXELS}) to assess context."
        )

    # 1. Statistical Moments
    mean_anomaly = float(np.mean(anomaly_pixels))
    std_anomaly = float(np.std(anomaly_pixels))
    mean_bg = float(np.mean(bg_pixels))
    std_bg = float(np.std(bg_pixels))

    # 2. Backscatter Intensity Difference & Local Contrast
    intensity_diff = abs(mean_anomaly - mean_bg)
    # Weber contrast: |I_anomaly - I_bg| / (I_bg + eps)
    weber_contrast = intensity_diff / (mean_bg + 1e-4)

    # Michelson contrast: (I_max - I_min) / (I_max + I_min + eps)
    michelson_contrast = intensity_diff / (mean_anomaly + mean_bg + 1e-4)

    # 3. Background Uniformity (higher when seabed is flat/homogeneous)
    background_uniformity = 1.0 / (1.0 + std_bg)

    # 4. Intensity Distribution Distance (Earth Mover's / Wasserstein Distance)
    emd_distance = float(wasserstein_distance(anomaly_pixels, bg_pixels))

    # 5. Normalized Context Score [0.0, 1.0]
    # Strong backscatter contrast and distributional divergence from the local seabed
    # indicate an acoustic intruder standing out from ambient sediment.
    contrast_score = sigmoid_score(weber_contrast, center=0.35, slope=4.0)
    distribution_score = sigmoid_score(emd_distance, center=20.0, slope=0.15)
    std_diff_score = linear_score(abs(std_anomaly - std_bg), min_val=0.0, max_val=30.0)

    raw_score = 0.50 * contrast_score + 0.35 * distribution_score + 0.15 * std_diff_score
    final_score = clamp_score(raw_score)

    features: Dict[str, Any] = {
        "mean_anomaly_intensity": round(mean_anomaly, 2),
        "std_anomaly_intensity": round(std_anomaly, 2),
        "mean_background_intensity": round(mean_bg, 2),
        "std_background_intensity": round(std_bg, 2),
        "intensity_difference": round(intensity_diff, 2),
        "weber_contrast": round(weber_contrast, 4),
        "michelson_contrast": round(michelson_contrast, 4),
        "background_uniformity": round(background_uniformity, 4),
        "distribution_wasserstein_distance": round(emd_distance, 2),
        "sampled_background_pixels": len(bg_pixels),
    }

    return EvidenceResult(
        available=True,
        score=round(final_score, 4),
        features=features,
        reason=None,
    )
