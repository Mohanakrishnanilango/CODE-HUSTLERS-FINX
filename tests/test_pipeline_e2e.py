import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_anomaly_detector
from app.main import app
from app.schemas.survey import SurveyMetadata
from app.services.anomaly_detector.base import (
    AnomalyDetector,
    AnomalyDetectionResult,
    AnomalyRegion,
)


class CustomTestDetector(AnomalyDetector):
    """A custom test detector simulating teammate's future model plugged in via dependency injection."""

    def predict(self, image: np.ndarray, metadata=None) -> AnomalyDetectionResult:
        h, w = image.shape[:2]
        mask = np.zeros((h, w), dtype=np.uint8)
        # Create a 30x30 square anomaly in the center
        mask[80:110, 80:110] = 255

        return AnomalyDetectionResult(
            regions=[
                AnomalyRegion(
                    region_id="teammate_simulated_01",
                    mask=mask,
                    bbox=(80, 80, 30, 30),
                    anomaly_score=0.92,
                )
            ]
        )


def test_end_to_end_pipeline_with_swapped_detector(client: TestClient, sample_sss_image_bytes: bytes):
    """
    Verifies that the teammate's model can be injected cleanly via dependency injection
    and the entire pipeline (evidence extraction, fusion, geolocation, ranking, DB, API)
    runs without modifying a single line of backend code.
    """
    # Override dependency with custom detector
    app.dependency_overrides[get_anomaly_detector] = lambda: CustomTestDetector()

    try:
        files = {"file": ("teammate_test.png", sample_sss_image_bytes, "image/png")}
        data = {
            "latitude": "12.9234",
            "longitude": "74.8456",
            "heading": "180.0",
            "resolution": "0.08",
            "nadir_column": "100",
            "enable_visual_debug": "true",
        }

        response = client.post("/api/detections/analyze", files=files, data=data)
        assert response.status_code == 201
        payload = response.json()

        assert payload["detector_used"] == "CustomTestDetector"
        assert payload["total_detections"] == 1

        det = payload["detections"][0]
        assert det["region_id"] == "teammate_simulated_01"
        assert det["anomaly_score"] == pytest.approx(0.92, abs=1e-3)
        assert det["final_confidence"] > 0.30
        assert det["priority"] in ("LOW", "MEDIUM", "HIGH")
        assert det["geolocation"]["available"] is True
        assert det["geolocation"]["latitude"] is not None

        # Verify DB retrieval
        det_id = det["detection_id"]
        check_res = client.get(f"/api/detections/{det_id}")
        assert check_res.status_code == 200
        assert check_res.json()["region_id"] == "teammate_simulated_01"

    finally:
        # Clean up dependency override
        app.dependency_overrides.pop(get_anomaly_detector, None)
