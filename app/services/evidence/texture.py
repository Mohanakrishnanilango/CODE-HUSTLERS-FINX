import math
from typing import Any, Dict, List, Optional, Tuple
import cv2
import numpy as np
from skimage.feature import graycomatrix, graycoprops, local_binary_pattern

from app.core.config import settings
from app.core.logging import logger
from app.schemas.evidence import EvidenceResult
from app.utils.image_processing import quantize_grayscale, create_annular_context_mask
from app.utils.normalization import clamp_score, sigmoid_score


def _compute_masked_glcm_properties(
    image: np.ndarray,
    mask: np.ndarray,
    num_levels: int = 16,
    distances: Optional[List[int]] = None,
    angles: Optional[List[float]] = None,
) -> Optional[Dict[str, float]]:
    """
    Computes GLCM properties strictly on pixels within `mask`.
    Eliminates rectangular bounding-box leakage by setting unmasked pixels
    to an ignore label `num_levels`, computing GLCM with `levels = num_levels + 1`,
    slicing `glcm[0:num_levels, 0:num_levels]`, and normalizing valid transitions.
    """
    if distances is None:
        distances = settings.GLCM_DISTANCES
    if angles is None:
        angles = [0.0, np.pi / 4.0, np.pi / 2.0, 3.0 * np.pi / 4.0]

    valid_pixel_count = int(np.count_nonzero(mask))
    if valid_pixel_count < settings.GLCM_MIN_VALID_PIXELS:
        return None

    # Crop to bounding box of the active mask with margin = max(distances)
    y_indices, x_indices = np.where(mask > 0)
    if len(y_indices) == 0:
        return None

    margin = max(distances)
    min_y = max(0, int(np.min(y_indices)) - margin)
    max_y = min(image.shape[0], int(np.max(y_indices)) + margin + 1)
    min_x = max(0, int(np.min(x_indices)) - margin)
    max_x = min(image.shape[1], int(np.max(x_indices)) + margin + 1)

    sub_img = image[min_y:max_y, min_x:max_x]
    sub_mask = mask[min_y:max_y, min_x:max_x]

    # Quantize to [0, num_levels - 1]
    quantized = quantize_grayscale(sub_img, num_levels=num_levels)

    # Assign ignore label `num_levels` to all non-mask pixels
    ignore_label = num_levels
    masked_quantized = np.where(sub_mask > 0, quantized, ignore_label).astype(np.uint8)

    # Compute GLCM with (num_levels + 1) levels
    raw_glcm = graycomatrix(
        masked_quantized,
        distances=distances,
        angles=angles,
        levels=num_levels + 1,
        symmetric=True,
        normed=False,
    )

    # Slice strictly valid transitions between masked pixels
    valid_glcm = raw_glcm[0:num_levels, 0:num_levels, :, :].astype(np.float64)

    # Normalize each (distance, angle) slice
    norm_glcm = np.zeros_like(valid_glcm)
    total_valid_pairs = 0.0

    for d_idx in range(len(distances)):
        for a_idx in range(len(angles)):
            slice_sum = np.sum(valid_glcm[:, :, d_idx, a_idx])
            if slice_sum > 0:
                norm_glcm[:, :, d_idx, a_idx] = valid_glcm[:, :, d_idx, a_idx] / slice_sum
                total_valid_pairs += slice_sum

    if total_valid_pairs == 0:
        return None

    # Compute standard Haralick features across distances and angles
    contrast = float(np.mean(graycoprops(norm_glcm, "contrast")))
    dissimilarity = float(np.mean(graycoprops(norm_glcm, "dissimilarity")))
    homogeneity = float(np.mean(graycoprops(norm_glcm, "homogeneity")))
    energy = float(np.mean(graycoprops(norm_glcm, "energy")))
    correlation = float(np.mean(graycoprops(norm_glcm, "correlation")))

    return {
        "contrast": contrast,
        "dissimilarity": dissimilarity,
        "homogeneity": homogeneity,
        "energy": energy,
        "correlation": correlation,
        "valid_pixels": valid_pixel_count,
    }


def _compute_lbp_features(
    image: np.ndarray,
    mask: np.ndarray,
    radius: float = 1.0,
    n_points: int = 8,
) -> Optional[np.ndarray]:
    """Computes normalized LBP histogram strictly inside mask."""
    if np.count_nonzero(mask) < 16:
        return None

    lbp = local_binary_pattern(image, n_points, radius, method="uniform")
    valid_lbp = lbp[mask > 0]
    n_bins = n_points + 2
    hist, _ = np.histogram(valid_lbp, bins=n_bins, range=(0, n_bins), density=True)
    return hist


def analyze_texture(
    image: np.ndarray,
    anomaly_mask: np.ndarray,
    background_mask: Optional[np.ndarray] = None,
    shadow_mask: Optional[np.ndarray] = None,
    num_levels: Optional[int] = None,
) -> EvidenceResult:
    """
    Analyzes micro-texture inside the anomaly candidate and compares it against
    the local ambient seafloor using masked GLCM and optional LBP descriptors.
    """
    if num_levels is None:
        num_levels = settings.GLCM_NUM_LEVELS

    if anomaly_mask is None or np.count_nonzero(anomaly_mask) < settings.GLCM_MIN_VALID_PIXELS:
        return EvidenceResult(
            available=False,
            score=None,
            features={},
            reason=f"Insufficient valid pixels in anomaly mask for GLCM (< {settings.GLCM_MIN_VALID_PIXELS} px)."
        )

    # 1. Compute Anomaly Texture
    anomaly_props = _compute_masked_glcm_properties(
        image=image,
        mask=anomaly_mask,
        num_levels=num_levels,
    )

    if anomaly_props is None:
        return EvidenceResult(
            available=False,
            score=None,
            features={},
            reason="GLCM calculation yielded zero valid pixel transitions inside anomaly mask."
        )

    # 2. Compute Background Texture
    if background_mask is None or np.count_nonzero(background_mask) < settings.CONTEXT_MIN_BACKGROUND_PIXELS:
        background_mask = create_annular_context_mask(
            mask=anomaly_mask,
            shadow_mask=shadow_mask,
            dilation_radius=settings.CONTEXT_DILATION_RADIUS_PX,
        )

    bg_props = _compute_masked_glcm_properties(
        image=image,
        mask=background_mask,
        num_levels=num_levels,
    )

    features: Dict[str, Any] = {
        "anomaly_glcm": {k: round(v, 4) if isinstance(v, float) else v for k, v in anomaly_props.items()},
        "background_glcm": {k: round(v, 4) if isinstance(v, float) else v for k, v in bg_props.items()} if bg_props else None,
    }

    # 3. Calculate Deltas and Normalized Evidence Score
    if bg_props is not None:
        delta_contrast = (anomaly_props["contrast"] - bg_props["contrast"]) / (bg_props["contrast"] + 1e-4)
        delta_dissimilarity = anomaly_props["dissimilarity"] - bg_props["dissimilarity"]
        delta_homogeneity = bg_props["homogeneity"] - anomaly_props["homogeneity"]
        delta_energy = bg_props["energy"] - anomaly_props["energy"]

        features["deltas"] = {
            "relative_contrast_delta": round(delta_contrast, 4),
            "dissimilarity_delta": round(delta_dissimilarity, 4),
            "homogeneity_reduction": round(delta_homogeneity, 4),
            "energy_reduction": round(delta_energy, 4),
        }

        # Optional LBP Chi-Square Distance
        lbp_a = _compute_lbp_features(image, anomaly_mask)
        lbp_bg = _compute_lbp_features(image, background_mask)
        if lbp_a is not None and lbp_bg is not None:
            chi_sq = 0.5 * np.sum(((lbp_a - lbp_bg) ** 2) / (lbp_a + lbp_bg + 1e-10))
            features["lbp_chi_square_distance"] = round(float(chi_sq), 4)

        # Normalized texture evidence score [0.0, 1.0]:
        # Elevated texture contrast and heterogeneity relative to seabed indicates fibrous netting mesh
        contrast_score = sigmoid_score(delta_contrast, center=0.30, slope=3.0)
        homogeneity_score = sigmoid_score(delta_homogeneity, center=0.05, slope=8.0)
        dissim_score = sigmoid_score(delta_dissimilarity, center=0.20, slope=4.0)

        raw_score = 0.40 * contrast_score + 0.35 * homogeneity_score + 0.25 * dissim_score
        final_score = clamp_score(raw_score)
        reason = None
    else:
        # Fallback when background has too few pixels (e.g. at edge of image)
        features["deltas"] = None
        # Score anomaly's intrinsic contrast and dissimilarity
        intrin_contrast = sigmoid_score(anomaly_props["contrast"], center=1.5, slope=1.5)
        intrin_homo = 1.0 - anomaly_props["homogeneity"]
        final_score = clamp_score(0.60 * intrin_contrast + 0.40 * intrin_homo)
        reason = "Background seafloor had insufficient valid pixels; texture scored on intrinsic anomaly variance only."

    return EvidenceResult(
        available=True,
        score=round(final_score, 4),
        features=features,
        reason=reason,
    )
