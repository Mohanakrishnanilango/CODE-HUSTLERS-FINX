from typing import Any, Dict, List, Optional, Tuple
import os
import cv2
import numpy as np
import torch
from ultralytics import YOLO

from app.core.config import settings
from app.core.logging import logger
from app.services.anomaly_detector.base import (
    AnomalyDetector,
    AnomalyDetectionResult,
    AnomalyRegion,
)


# Map YOLO-B class names to natural/unnatural categories
_UNNATURAL_CLASSES = {
    "ghost_net",
    "shipwreck",
    "mine_cylinder",
    "crab_pot",
    "submarine_pipeline",
    "Artificial_Object",
    "artificial_object",
}
_NATURAL_LABELS = {"natural", "background", "seabed", "sand", "rock"}


class DualYOLODetector(AnomalyDetector):
    """
    Dual-model YOLO voting classifier for ghost net detection.

    Model A (YOLO-A): Binary detector — classifies regions as Artificial_Object or background.
    Model B (YOLO-B): Multi-class classifier — classifies into crab_pot, submarine_pipeline,
                       shipwreck, ghost_net, mine_cylinder, Artificial_Object.

    Decision Matrix:
        YOLO-A: artificial  + YOLO-B: (any positive)  → STRONG POSITIVE
        YOLO-A: (anything)   + YOLO-B: unnatural       → SUPPORTING POSITIVE
        YOLO-A: artificial  + YOLO-B: natural           → UNCERTAIN
        YOLO-A: nothing      + YOLO-B: unnatural        → INVESTIGATE
        YOLO-A: nothing      + YOLO-B: nothing           → BACKGROUND (no detection)
    """

    def __init__(
        self,
        model_a_path: Optional[str] = None,
        model_b_path: Optional[str] = None,
        confidence_threshold: float = 0.25,
        min_bbox_ratio: float = 0.03,
        device: str = "cpu",
    ):
        self.model_a_path = model_a_path or os.path.join("weights", "model_a.pt")
        self.model_b_path = model_b_path or os.path.join("weights", "model_b.pt")
        self.confidence_threshold = confidence_threshold
        self.min_bbox_ratio = min_bbox_ratio
        self.device = device
        self.model_a = None
        self.model_b = None
        self._load_models()

    def _load_models(self):
        """Load both YOLO models."""
        try:
            if os.path.exists(self.model_a_path):
                self.model_a = YOLO(self.model_a_path)
                logger.info(f"Loaded YOLO Model A from {self.model_a_path}: {self.model_a.names}")
            else:
                logger.warning(f"Model A weights not found at {self.model_a_path}")
        except Exception as e:
            logger.error(f"Failed to load Model A from {self.model_a_path}: {e}")

        try:
            if os.path.exists(self.model_b_path):
                self.model_b = YOLO(self.model_b_path)
                logger.info(f"Loaded YOLO Model B from {self.model_b_path}: {self.model_b.names}")
            else:
                logger.warning(f"Model B weights not found at {self.model_b_path}")
        except Exception as e:
            logger.error(f"Failed to load Model B from {self.model_b_path}: {e}")

    def _run_yolo(self, model: Any, image_bgr: np.ndarray) -> List[Dict]:
        """
        Run YOLO inference and extract normalized bounding boxes and confidences.
        Returns list of dicts: {bbox: (x, y, w, h), confidence: float, class_id: int, class_name: str}
        """
        if model is None:
            return []

        h0, w0 = image_bgr.shape[:2]

        try:
            results = model.predict(
                image_bgr,
                conf=self.confidence_threshold,
                verbose=False,
                device=self.device,
            )
            if not results or len(results) == 0:
                return []
            res = results[0]
            if res.boxes is None or len(res.boxes) == 0:
                return []

            boxes = res.boxes.xyxy.cpu().numpy()
            confs = res.boxes.conf.cpu().numpy()
            cls_ids = res.boxes.cls.cpu().numpy().astype(int)
            names = model.names or {}

            parsed = []
            for (x1, y1, x2, y2), conf, cls_id in zip(boxes, confs, cls_ids):
                # Clamp coordinates to original image bounds
                x1_c = max(0, min(float(x1), float(w0)))
                y1_c = max(0, min(float(y1), float(h0)))
                x2_c = max(0, min(float(x2), float(w0)))
                y2_c = max(0, min(float(y2), float(h0)))
                bw = x2_c - x1_c
                bh = y2_c - y1_c

                min_dim_w = w0 * self.min_bbox_ratio
                min_dim_h = h0 * self.min_bbox_ratio
                if bw < min_dim_w or bh < min_dim_h:
                    continue

                class_name = names.get(cls_id, f"class_{cls_id}")
                parsed.append({
                    "bbox": (int(x1_c), int(y1_c), int(bw), int(bh)),
                    "confidence": float(conf),
                    "class_id": int(cls_id),
                    "class_name": class_name,
                })
            return parsed

        except Exception as e:
            logger.error(f"Error in YOLO inference: {e}")
            return []

    def _create_mask_from_bbox(
        self,
        bbox: Tuple[int, int, int, int],
        image: np.ndarray,
    ) -> np.ndarray:
        """Create highlight mask within bounding box using intensity thresholding."""
        h_img, w_img = image.shape[:2]
        mask = np.zeros((h_img, w_img), dtype=np.uint8)
        x, y, w, h = bbox

        x = max(0, min(x, w_img - 1))
        y = max(0, min(y, h_img - 1))
        w = max(1, min(w, w_img - x))
        h = max(1, min(h, h_img - y))

        if image.ndim == 3:
            crop = cv2.cvtColor(image[y:y+h, x:x+w], cv2.COLOR_BGR2GRAY)
        else:
            crop = image[y:y+h, x:x+w]

        # Extract acoustic highlight within bounding box
        thresh = np.mean(crop) + 0.3 * np.std(crop)
        crop_mask = (crop >= thresh).astype(np.uint8) * 255
        pos_ratio = np.count_nonzero(crop_mask) / (w * h)

        if 0.05 <= pos_ratio <= 0.95:
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
            crop_mask = cv2.morphologyEx(crop_mask, cv2.MORPH_CLOSE, kernel)
            mask[y:y+h, x:x+w] = crop_mask
        else:
            mask[y:y+h, x:x+w] = 255

        return mask

    def _vote(
        self,
        det_a: List[Dict],
        det_b: List[Dict],
    ) -> Tuple[str, float, str, Dict]:
        """
        Apply dual-model voting logic.

        Returns: (verdict, combined_score, classification, audit)
        """
        audit = {
            "model_a_detections": len(det_a),
            "model_b_detections": len(det_b),
            "model_a_classes": [d["class_name"] for d in det_a],
            "model_b_classes": [d["class_name"] for d in det_b],
        }

        has_a = len(det_a) > 0
        has_b = len(det_b) > 0

        if not has_a and not has_b:
            return "BACKGROUND", 0.0, "none", audit

        # Get best scores
        best_a = max((d["confidence"] for d in det_a), default=0.0)
        best_b = max((d["confidence"] for d in det_b), default=0.0)

        b_is_unnatural = any(d["class_name"] in _UNNATURAL_CLASSES for d in det_b)
        b_class_name = next(
            (d["class_name"] for d in det_b if d["class_name"] in _UNNATURAL_CLASSES),
            det_b[0]["class_name"] if det_b else "none",
        )

        # Decision matrix — Model A (best.pt) gets preference
        W_A = 0.6  # Model A weight (preferred)
        W_B = 0.4  # Model B weight

        if has_a and has_b:
            # Both models detected — strong agreement
            combined = best_a * W_A + best_b * W_B
            audit["logic"] = "both_detected"
            if b_is_unnatural:
                audit["verdict_reason"] = "YOLO-A: artificial + YOLO-B: unnatural → STRONG POSITIVE"
                return "STRONG_POSITIVE", combined, b_class_name, audit
            else:
                audit["verdict_reason"] = "YOLO-A: artificial + YOLO-B: other → UNCERTAIN"
                return "UNCERTAIN", combined * 0.7, b_class_name, audit

        elif has_a and not has_b:
            # Only Model A detected
            audit["logic"] = "only_model_a"
            audit["verdict_reason"] = "YOLO-A: artificial + YOLO-B: nothing → CONFIRMED"
            return "CONFIRMED", best_a, "artificial_object", audit

        else:
            # Only Model B detected — lower confidence without A confirmation
            audit["logic"] = "only_model_b"
            if b_is_unnatural:
                audit["verdict_reason"] = "YOLO-A: nothing + YOLO-B: unnatural → INVESTIGATE"
                return "INVESTIGATE", best_b * 0.6, b_class_name, audit
            else:
                audit["verdict_reason"] = "YOLO-A: nothing + YOLO-B: other → INVESTIGATE"
                return "INVESTIGATE", best_b * 0.4, b_class_name, audit

    def predict(
        self,
        image: np.ndarray,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AnomalyDetectionResult:
        """
        Run both YOLO models on the SSS image, apply voting logic,
        and convert results into AnomalyRegion objects for the evidence pipeline.
        """
        logger.info("DualYOLODetector: Processing image of shape %s", image.shape)

        if self.model_a is None and self.model_b is None:
            logger.error("Neither model is loaded. Falling back to no detections.")
            return AnomalyDetectionResult(
                regions=[], raw_anomaly_map=None,
                processing_metadata={"detector": "DualYOLODetector", "error": "no models loaded"},
            )

        # Convert grayscale SSS to BGR for YOLO (expects 3-channel)
        if image.ndim == 2:
            img_bgr = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        else:
            img_bgr = image

        # Run both models
        det_a = self._run_yolo(self.model_a, img_bgr) if self.model_a else []
        det_b = self._run_yolo(self.model_b, img_bgr) if self.model_b else []
        logger.info(f"DualYOLO: Model A found {len(det_a)} region(s), Model B found {len(det_b)} region(s)")

        # Merge detections: combine overlapping bboxes from both models
        all_bboxes = []
        for d in det_a:
            all_bboxes.append({**d, "source": "YOLO-A"})
        for d in det_b:
            all_bboxes.append({**d, "source": "YOLO-B"})

        # If no detections from either model, return empty
        if not all_bboxes:
            return AnomalyDetectionResult(
                regions=[], raw_anomaly_map=None,
                processing_metadata={
                    "detector": "DualYOLODetector",
                    "model_a_detections": 0,
                    "model_b_detections": 0,
                    "verdict": "BACKGROUND",
                },
            )

        # Cluster overlapping bboxes (IoU > 0.3 = same region)
        regions = []
        used = set()

        for i, det_i in enumerate(all_bboxes):
            if i in used:
                continue

            # Find overlapping detections
            cluster = [det_i]
            used.add(i)
            xi, yi, wi, hi = det_i["bbox"]

            for j, det_j in enumerate(all_bboxes):
                if j in used:
                    continue
                xj, yj, wj, hj = det_j["bbox"]

                # IoU calculation
                x_overlap = max(0, min(xi+wi, xj+wj) - max(xi, xj))
                y_overlap = max(0, min(yi+hi, yj+hj) - max(yi, yj))
                intersection = x_overlap * y_overlap
                union = wi*hi + wj*hj - intersection
                iou = intersection / union if union > 0 else 0

                if iou > 0.3:
                    cluster.append(det_j)
                    used.add(j)

            # Get best bbox from cluster
            best = max(cluster, key=lambda d: d["confidence"])
            x, y, w, h = best["bbox"]

            # Run voting on cluster members
            a_dets = [d for d in cluster if d["source"] == "YOLO-A"]
            b_dets = [d for d in cluster if d["source"] == "YOLO-B"]
            verdict, score, classification, audit = self._vote(a_dets, b_dets)

            # Skip BACKGROUND verdicts
            if verdict == "BACKGROUND":
                continue

            # Skip very small regions even after voting
            area_ratio = (w * h) / (image.shape[0] * image.shape[1])
            if area_ratio < self.min_bbox_ratio * self.min_bbox_ratio:
                continue

            # Apply confidence penalty for small detections
            if area_ratio < 0.01:
                score *= 0.5
            elif area_ratio < 0.02:
                score *= 0.75

            # Create mask
            mask = self._create_mask_from_bbox((x, y, w, h), image)

            region_id = f"dual_{len(regions)+1:02d}_{classification}"
            regions.append(AnomalyRegion(
                region_id=region_id,
                mask=mask,
                bbox=(x, y, w, h),
                anomaly_score=min(score, 1.0),
            ))

        logger.info(f"DualYOLO: Produced {len(regions)} merged region(s) for evidence pipeline")

        return AnomalyDetectionResult(
            regions=regions,
            raw_anomaly_map=None,
            processing_metadata={
                "detector": "DualYOLODetector",
                "model_a": self.model_a_path,
                "model_b": self.model_b_path,
                "model_a_detections": len(det_a),
                "model_b_detections": len(det_b),
                "merged_regions": len(regions),
            },
        )
