from typing import Any, Dict, List, Optional
import numpy as np

from app.core.logging import logger
from app.services.anomaly_detector.base import (
    AnomalyDetector,
    AnomalyDetectionResult,
    AnomalyRegion,
)
from app.services.anomaly_detector.unet_detector import UNetAnomalyDetector
from app.services.anomaly_detector.dual_yolo_detector import DualYOLODetector


class HybridAnomalyDetector(AnomalyDetector):
    """
    Ensemble anomaly detector combining:
    1. UNet segmentation for fine pixel-level contour and mask extraction
    2. Dual YOLO for object proposal verification and voting

    When both detectors highlight overlapping seafloor anomalies, scores are fused
    and boosted. High-resolution UNet masks are retained for downstream evidence analysis.
    """

    def __init__(
        self,
        unet_model_path: Optional[str] = None,
        unet_threshold: float = 0.5,
        yolo_a_path: Optional[str] = None,
        yolo_b_path: Optional[str] = None,
        yolo_threshold: float = 0.25,
        device: str = "cpu",
    ):
        self.unet = UNetAnomalyDetector(
            model_path=unet_model_path,
            confidence_threshold=unet_threshold,
            device=device,
        )
        self.dual_yolo = DualYOLODetector(
            model_a_path=yolo_a_path,
            model_b_path=yolo_b_path,
            confidence_threshold=yolo_threshold,
            device=device,
        )

    def predict(
        self,
        image: np.ndarray,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AnomalyDetectionResult:
        logger.info("HybridAnomalyDetector: Executing UNet + YOLO ensemble")
        
        unet_res = self.unet.predict(image, metadata=metadata)
        yolo_res = self.dual_yolo.predict(image, metadata=metadata)

        unet_regions = unet_res.regions
        yolo_regions = yolo_res.regions

        merged_regions: List[AnomalyRegion] = []
        matched_yolo = set()

        for u_reg in unet_regions:
            ux, uy, uw, uh = u_reg.bbox
            best_iou = 0.0
            best_yolo_idx = -1

            for y_idx, y_reg in enumerate(yolo_regions):
                yx, yy, yw, yh = y_reg.bbox
                x_overlap = max(0, min(ux + uw, yx + yw) - max(ux, yx))
                y_overlap = max(0, min(uy + uh, yy + yh) - max(uy, yy))
                intersection = x_overlap * y_overlap
                union = uw * uh + yw * yh - intersection
                iou = intersection / union if union > 0 else 0

                if iou > best_iou:
                    best_iou = iou
                    best_yolo_idx = y_idx

            if best_iou > 0.2 and best_yolo_idx >= 0:
                matched_yolo.add(best_yolo_idx)
                y_reg = yolo_regions[best_yolo_idx]
                fused_score = min(1.0, u_reg.anomaly_score * 0.6 + y_reg.anomaly_score * 0.4 + 0.1)
                merged_regions.append(
                    AnomalyRegion(
                        region_id=f"hybrid_{len(merged_regions)+1:02d}_confirmed",
                        mask=u_reg.mask,
                        bbox=u_reg.bbox,
                        anomaly_score=round(fused_score, 4),
                        confidence_map=u_reg.confidence_map,
                    )
                )
            else:
                merged_regions.append(u_reg)

        for y_idx, y_reg in enumerate(yolo_regions):
            if y_idx not in matched_yolo:
                merged_regions.append(
                    AnomalyRegion(
                        region_id=f"hybrid_{len(merged_regions)+1:02d}_{y_reg.region_id}",
                        mask=y_reg.mask,
                        bbox=y_reg.bbox,
                        anomaly_score=round(y_reg.anomaly_score * 0.85, 4),
                        confidence_map=y_reg.confidence_map,
                    )
                )

        merged_regions.sort(key=lambda r: r.anomaly_score, reverse=True)

        return AnomalyDetectionResult(
            regions=merged_regions,
            raw_anomaly_map=unet_res.raw_anomaly_map,
            processing_metadata={
                "detector": "HybridAnomalyDetector",
                "unet_candidates": len(unet_regions),
                "yolo_candidates": len(yolo_regions),
                "total_merged": len(merged_regions),
            },
        )
