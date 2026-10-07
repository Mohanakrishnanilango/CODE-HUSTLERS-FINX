import os
from typing import Any, Dict, List, Optional, Tuple
import cv2
import numpy as np
import torch
import segmentation_models_pytorch as smp

from app.core.config import settings
from app.core.logging import logger
from app.services.anomaly_detector.base import (
    AnomalyDetector,
    AnomalyDetectionResult,
    AnomalyRegion,
)


class UNetAnomalyDetector(AnomalyDetector):
    """
    ResNet-34 UNet segmentation model for Side-Scan Sonar (SSS) ghost net detection.
    
    Loads pre-trained weights from `ml/best_unet.pth` and outputs pixel-accurate
    segmentation masks, contours, and precise bounding boxes for seafloor anomalies.
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        confidence_threshold: float = 0.5,
        min_area_px: int = 100,
        device: str = "cpu",
    ):
        self.model_path = model_path or getattr(settings, "UNET_MODEL_PATH", "ml/best_unet.pth")
        self.confidence_threshold = confidence_threshold
        self.min_area_px = min_area_px
        self.device = torch.device(device if torch.cuda.is_available() and device == "cuda" else "cpu")
        self.model = None
        self._load_model()

    def _load_model(self) -> None:
        """Loads ResNet34-UNet architecture and weights from checkpoint."""
        if not os.path.exists(self.model_path):
            logger.error("UNet weights checkpoint not found at %s", self.model_path)
            return

        try:
            self.model = smp.Unet(
                encoder_name="resnet34",
                in_channels=3,
                classes=1,
                encoder_weights=None,
            )
            state = torch.load(self.model_path, map_location=self.device, weights_only=False)
            if isinstance(state, dict):
                if "model_state_dict" in state:
                    state = state["model_state_dict"]
                elif "state_dict" in state:
                    state = state["state_dict"]
            self.model.load_state_dict(state)
            self.model.to(self.device).eval()
            param_count = sum(p.numel() for p in self.model.parameters())
            logger.info(
                "Loaded UNet model from %s (%s params) on %s",
                self.model_path,
                f"{param_count:,}",
                self.device,
            )
        except Exception as e:
            logger.error("Failed to load UNet model from %s: %s", self.model_path, e)
            self.model = None

    def predict(
        self,
        image: np.ndarray,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AnomalyDetectionResult:
        """
        Executes UNet segmentation on the input SSS image.
        
        Args:
            image: 2D uint8 grayscale or 3D uint8 BGR/RGB image.
            metadata: Optional survey/acoustic acquisition metadata.
            
        Returns:
            AnomalyDetectionResult containing pixel-accurate regions and bounding boxes.
        """
        if self.model is None:
            logger.error("UNet model is uninitialized. Returning zero detections.")
            return AnomalyDetectionResult(
                regions=[],
                raw_anomaly_map=None,
                processing_metadata={"detector": "UNetAnomalyDetector", "error": "model not loaded"},
            )

        h0, w0 = image.shape[:2]

        # Convert image to 3-channel RGB float tensor
        if image.ndim == 2:
            img_rgb = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
        elif image.shape[2] == 3:
            img_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        else:
            img_rgb = cv2.cvtColor(image[:, :, :3], cv2.COLOR_BGR2RGB)

        # Standard high-resolution SSS input tile (640x640)
        target_size = 640
        img_resized = cv2.resize(img_rgb, (target_size, target_size), interpolation=cv2.INTER_LINEAR)
        tensor = torch.from_numpy(img_resized.transpose(2, 0, 1)).float().unsqueeze(0) / 255.0
        tensor = tensor.to(self.device)

        with torch.no_grad():
            logits = self.model(tensor)
            probs_640 = torch.sigmoid(logits)[0, 0].cpu().numpy()

        # Rescale probability map back to original input image dimensions
        anomaly_map = cv2.resize(probs_640, (w0, h0), interpolation=cv2.INTER_LINEAR)
        binary_mask = (anomaly_map >= self.confidence_threshold).astype(np.uint8) * 255

        # Morphological clean up to suppress single-pixel speckle noise
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        binary_mask_clean = cv2.morphologyEx(binary_mask, cv2.MORPH_OPEN, kernel)

        # Find external contours of detected anomalies
        contours, _ = cv2.findContours(binary_mask_clean, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        regions: List[AnomalyRegion] = []
        for idx, cnt in enumerate(contours):
            area = cv2.contourArea(cnt)
            if area < self.min_area_px:
                continue

            x, y, bw, bh = cv2.boundingRect(cnt)

            # Clamp coordinates to original image boundaries
            x = max(0, min(int(x), w0 - 1))
            y = max(0, min(int(y), h0 - 1))
            bw = max(1, min(int(bw), w0 - x))
            bh = max(1, min(int(bh), h0 - y))

            # Isolate mask for this specific candidate region
            region_mask = np.zeros((h0, w0), dtype=np.uint8)
            cv2.drawContours(region_mask, [cnt], -1, 255, -1)

            # Compute regional anomaly score (mean probability within mask)
            patch_prob = anomaly_map[y:y+bh, x:x+bw]
            patch_mask = region_mask[y:y+bh, x:x+bw]
            active_pixels = patch_prob[patch_mask > 0]
            if len(active_pixels) > 0:
                score = float(np.mean(active_pixels))
            else:
                score = float(np.max(patch_prob)) if patch_prob.size > 0 else self.confidence_threshold

            score = float(min(1.0, max(0.0, score)))

            region_id = f"unet_{len(regions)+1:02d}_ghost_net"
            regions.append(
                AnomalyRegion(
                    region_id=region_id,
                    mask=region_mask,
                    bbox=(x, y, bw, bh),
                    anomaly_score=round(score, 4),
                    confidence_map=patch_prob,
                )
            )

        # Sort candidate regions by anomaly score descending
        regions.sort(key=lambda r: r.anomaly_score, reverse=True)
        logger.info("UNetAnomalyDetector: Segmented %d candidate anomaly region(s)", len(regions))

        return AnomalyDetectionResult(
            regions=regions,
            raw_anomaly_map=anomaly_map,
            processing_metadata={
                "detector": "UNetAnomalyDetector",
                "model_path": self.model_path,
                "confidence_threshold": self.confidence_threshold,
                "regions_detected": len(regions),
            },
        )
