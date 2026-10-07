from functools import lru_cache
from typing import Optional
from app.core.config import settings
from app.core.logging import logger
from app.database.session import get_db
from app.services.anomaly_detector.base import AnomalyDetector
from app.services.anomaly_detector.mock_detector import MockAnomalyDetector
from app.services.anomaly_detector.teammate_detector import TeammateAnomalyDetectorAdapter
from app.services.anomaly_detector.dual_yolo_detector import DualYOLODetector
from app.services.anomaly_detector.unet_detector import UNetAnomalyDetector
from app.services.anomaly_detector.hybrid_detector import HybridAnomalyDetector


def resolve_detector(backend_override: Optional[str] = None) -> AnomalyDetector:
    """
    Instantiates or resolves an AnomalyDetector based on backend name.
    Supports: 'unet', 'dual_yolo', 'hybrid', 'teammate', 'mock'.
    """
    backend = (backend_override or settings.DETECTOR_BACKEND).strip().lower()

    if backend == "unet":
        logger.info("Injecting UNetAnomalyDetector (ResNet34 UNet Segmentation: %s)", settings.UNET_MODEL_PATH)
        return UNetAnomalyDetector(
            model_path=settings.UNET_MODEL_PATH,
            confidence_threshold=settings.UNET_CONFIDENCE_THRESHOLD,
            min_area_px=settings.UNET_MIN_AREA_PX,
            device=settings.TEAMMATE_DEVICE,
        )
    elif backend == "dual_yolo":
        logger.info("Injecting DualYOLODetector (YOLO-A + YOLO-B voting)")
        return DualYOLODetector(
            model_a_path=settings.DUAL_YOLO_MODEL_A,
            model_b_path=settings.DUAL_YOLO_MODEL_B,
            confidence_threshold=settings.DUAL_YOLO_CONFIDENCE,
            device=settings.TEAMMATE_DEVICE,
        )
    elif backend == "hybrid":
        logger.info("Injecting HybridAnomalyDetector (UNet + Dual YOLO ensemble)")
        return HybridAnomalyDetector(
            unet_model_path=settings.UNET_MODEL_PATH,
            unet_threshold=settings.UNET_CONFIDENCE_THRESHOLD,
            yolo_a_path=settings.DUAL_YOLO_MODEL_A,
            yolo_b_path=settings.DUAL_YOLO_MODEL_B,
            yolo_threshold=settings.DUAL_YOLO_CONFIDENCE,
            device=settings.TEAMMATE_DEVICE,
        )
    elif backend == "teammate":
        logger.info("Injecting TeammateAnomalyDetectorAdapter")
        return TeammateAnomalyDetectorAdapter(
            model_path=settings.TEAMMATE_MODEL_PATH,
            device=settings.TEAMMATE_DEVICE,
        )
    else:
        logger.info("Injecting MockAnomalyDetector (Development / Test mode)")
        return MockAnomalyDetector()


@lru_cache()
def get_anomaly_detector() -> AnomalyDetector:
    """
    Cached dependency injection provider for the anomaly detector.
    Configured via DETECTOR_BACKEND setting.
    """
    return resolve_detector(settings.DETECTOR_BACKEND)
