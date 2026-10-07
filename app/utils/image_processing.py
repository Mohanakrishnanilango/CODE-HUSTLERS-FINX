import io
from typing import Optional, Tuple
import cv2
import numpy as np
from PIL import Image

from app.core.logging import logger


class ImageProcessingError(ValueError):
    """Raised when SSS image validation or decoding fails."""
    pass


def load_and_preprocess_image(image_bytes: bytes) -> np.ndarray:
    """
    Decodes and validates an uploaded SSS image.
    Supports PNG, JPEG, TIFF, GeoTIFF, BMP.
    Normalizes to single-channel 8-bit unsigned integer [0, 255].
    """
    if not image_bytes or len(image_bytes) == 0:
        raise ImageProcessingError("Empty image buffer received.")

    # Try OpenCV first
    np_arr = np.frombuffer(image_bytes, np.uint8)
    image = cv2.imdecode(np_arr, cv2.IMREAD_UNCHANGED)

    # If OpenCV failed (e.g. some TIFF / multi-band GeoTIFF formats), try Pillow
    if image is None:
        try:
            pil_img = Image.open(io.BytesIO(image_bytes))
            image = np.array(pil_img)
        except Exception as e:
            raise ImageProcessingError(f"Failed to decode image: {str(e)}")

    if image is None or image.size == 0:
        raise ImageProcessingError("Decoded image is empty.")

    # Convert multi-channel to single-channel grayscale
    if image.ndim == 3:
        if image.shape[2] == 4:
            # RGBA
            image = cv2.cvtColor(image, cv2.COLOR_BGRA2GRAY)
        elif image.shape[2] == 3:
            # RGB/BGR
            image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            # Multi-spectral or strange channel count: take first band
            image = image[:, :, 0]

    # Convert non-uint8 (e.g. 16-bit uint16 or 32-bit float sonar data) to 8-bit uint8
    if image.dtype != np.uint8:
        image = normalize_to_uint8(image)

    # Dimension validation
    min_dim = 32
    if image.shape[0] < min_dim or image.shape[1] < min_dim:
        raise ImageProcessingError(
            f"Image dimensions ({image.shape[0]}x{image.shape[1]}) too small; minimum is {min_dim}x{min_dim}."
        )

    logger.debug(f"Preprocessed image successfully: shape={image.shape}, dtype={image.dtype}")
    return image


def normalize_to_uint8(image: np.ndarray) -> np.ndarray:
    """
    Safely converts high-bitdepth or float imagery to 8-bit [0, 255]
    using robust percentile clipping (1st and 99th percentiles) to prevent
    acoustic transducer speckle spikes from squashing dynamic range.
    """
    if image.size == 0:
        return np.zeros((0, 0), dtype=np.uint8)

    p_low, p_high = np.percentile(image, (1.0, 99.0))
    if p_high <= p_low:
        p_low = float(np.min(image))
        p_high = float(np.max(image))

    if p_high <= p_low:
        # Zero variance image
        return np.zeros(image.shape, dtype=np.uint8)

    clipped = np.clip(image, p_low, p_high)
    normalized = (clipped - p_low) / (p_high - p_low) * 255.0
    return normalized.astype(np.uint8)


def quantize_grayscale(image: np.ndarray, num_levels: int = 16) -> np.ndarray:
    """
    Quantizes an 8-bit [0, 255] grayscale image into [0, num_levels - 1].
    Used to accelerate GLCM and reduce speckle noise sensitivity.
    """
    if num_levels < 2:
        raise ValueError("num_levels must be at least 2")

    # Map [0, 255] -> [0, num_levels - 1]
    scale = (num_levels - 1) / 255.0
    quantized = np.floor(image.astype(np.float32) * scale).astype(np.uint8)
    return np.clip(quantized, 0, num_levels - 1)


def create_annular_context_mask(
    mask: np.ndarray,
    shadow_mask: Optional[np.ndarray] = None,
    dilation_radius: int = 25,
) -> np.ndarray:
    """
    Creates an annular background ROI around an anomaly:
    1. Dilates the anomaly mask using an elliptical structuring element.
    2. Subtracts the anomaly mask itself to avoid self-contamination.
    3. Subtracts any detected acoustic shadow mask to prevent acoustic dropouts
       from polluting ambient seafloor statistics.
    """
    kernel = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE, (2 * dilation_radius + 1, 2 * dilation_radius + 1)
    )
    dilated = cv2.dilate(mask, kernel)

    # Exclude anomaly
    background = cv2.bitwise_and(dilated, cv2.bitwise_not(mask))

    # Exclude shadow if available
    if shadow_mask is not None and shadow_mask.shape == mask.shape:
        background = cv2.bitwise_and(background, cv2.bitwise_not(shadow_mask))

    return background
