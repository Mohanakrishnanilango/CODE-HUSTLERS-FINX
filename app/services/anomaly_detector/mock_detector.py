from typing import Any, Dict, List, Optional
import cv2
import numpy as np

from app.core.logging import logger
from app.services.anomaly_detector.base import (
    AnomalyDetector,
    AnomalyDetectionResult,
    AnomalyRegion,
)


class MockAnomalyDetector(AnomalyDetector):
    """
    Deterministic mock anomaly detector for development, staging, and automated testing.
    Produces realistic synthetic ghost-net anomaly candidates without requiring
    an external machine learning model.
    """

    def __init__(self, seed: int = 42, num_regions: int = 2):
        self.seed = seed
        self.num_regions = num_regions

    def predict(
        self,
        image: np.ndarray,
        metadata: Optional[Dict[str, Any]] = None
    ) -> AnomalyDetectionResult:
        logger.info("Executing MockAnomalyDetector on image of shape %s", image.shape)
        h, w = image.shape[:2]

        regions: List[AnomalyRegion] = []
        rng = np.random.RandomState(self.seed)

        # Region 1: Primary candidate (high score, irregular netting bundle)
        mask1 = np.zeros((h, w), dtype=np.uint8)
        # Position in upper-center/starboard quadrant
        cx1 = int(w * 0.58)
        cy1 = int(h * 0.45)
        # Generate an irregular, curvilinear polygon resembling snagged netting
        pts1 = np.array([
            [cx1 - 25, cy1 - 35],
            [cx1 - 5,  cy1 - 42],
            [cx1 + 22, cy1 - 28],
            [cx1 + 38, cy1 - 10],
            [cx1 + 45, cy1 + 15],
            [cx1 + 28, cy1 + 38],
            [cx1 + 5,  cy1 + 42],
            [cx1 - 18, cy1 + 30],
            [cx1 - 35, cy1 + 10],
            [cx1 - 38, cy1 - 18],
        ], dtype=np.int32)

        # Clip points to image bounds
        pts1[:, 0] = np.clip(pts1[:, 0], 0, w - 1)
        pts1[:, 1] = np.clip(pts1[:, 1], 0, h - 1)

        cv2.fillPoly(mask1, [pts1], 255)

        # Punch a small internal mesh hole to simulate open netting structure
        cv2.circle(mask1, (cx1 + 5, cy1 - 2), 6, 0, -1)

        x1, y1, bw1, bh1 = cv2.boundingRect(pts1)
        regions.append(
            AnomalyRegion(
                region_id="mock_region_01",
                mask=mask1,
                bbox=(int(x1), int(y1), int(bw1), int(bh1)),
                anomaly_score=0.92,
                confidence_map=None,
            )
        )

        # Region 2 (if requested and image is large enough): Secondary candidate
        if self.num_regions > 1 and h >= 120 and w >= 120:
            mask2 = np.zeros((h, w), dtype=np.uint8)
            cx2 = int(w * 0.28)
            cy2 = int(h * 0.70)
            pts2 = np.array([
                [cx2 - 15, cy2 - 8],
                [cx2 + 10, cy2 - 18],
                [cx2 + 25, cy2 + 5],
                [cx2 + 8,  cy2 + 20],
                [cx2 - 12, cy2 + 15],
            ], dtype=np.int32)
            pts2[:, 0] = np.clip(pts2[:, 0], 0, w - 1)
            pts2[:, 1] = np.clip(pts2[:, 1], 0, h - 1)

            cv2.fillPoly(mask2, [pts2], 255)
            x2, y2, bw2, bh2 = cv2.boundingRect(pts2)

            regions.append(
                AnomalyRegion(
                    region_id="mock_region_02",
                    mask=mask2,
                    bbox=(int(x2), int(y2), int(bw2), int(bh2)),
                    anomaly_score=0.62,
                    confidence_map=None,
                )
            )

        return AnomalyDetectionResult(
            regions=regions,
            raw_anomaly_map=None,
            processing_metadata={
                "detector": "MockAnomalyDetector",
                "seed": self.seed,
                "regions_generated": len(regions),
            },
        )
