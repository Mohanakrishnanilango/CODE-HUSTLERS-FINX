import os
import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.services.anomaly_detector.unet_detector import UNetAnomalyDetector
from app.services.anomaly_detector.dual_yolo_detector import DualYOLODetector
from app.services.anomaly_detector.hybrid_detector import HybridAnomalyDetector


def test_unet_detector_loading_and_prediction():
    """Verify UNet detector loads best_unet.pth and outputs accurate masks and bboxes."""
    model_path = "ml/best_unet.pth"
    assert os.path.exists(model_path), f"UNet model not found at {model_path}"

    detector = UNetAnomalyDetector(model_path=model_path, confidence_threshold=0.5)
    assert detector.model is not None

    test_img_path = "ml/data/drishti/test/images/synth_ghost_net_00001.png"
    img = cv2.imread(test_img_path)
    assert img is not None, f"Test image not found at {test_img_path}"
    h0, w0 = img.shape[:2]

    res = detector.predict(img)
    assert len(res.regions) >= 1
    top_region = res.regions[0]

    # Verify bounding box validity and alignment
    x, y, w, h = top_region.bbox
    assert 0 <= x < w0
    assert 0 <= y < h0
    assert w > 20
    assert h > 20
    assert x + w <= w0
    assert y + h <= h0

    # Ensure box is located around the actual ghost net anomaly (not stuck at 0, 2)
    assert x > 50, f"Expected x > 50 around ghost net, got {x}"
    assert y > 100, f"Expected y > 100 around ghost net, got {y}"

    # Verify mask
    assert top_region.mask.shape == (h0, w0)
    assert top_region.mask.dtype == np.uint8
    assert np.count_nonzero(top_region.mask) > 100
    assert top_region.anomaly_score >= 0.5


def test_unet_background_rejection():
    """Verify UNet produces 0 false positive detections on clear seafloor background."""
    detector = UNetAnomalyDetector(model_path="ml/best_unet.pth", confidence_threshold=0.5)
    bg_path = "ml/data/drishti/test/images/bg_1693569243.750_x2500.jpg"
    img = cv2.imread(bg_path)
    assert img is not None

    res = detector.predict(img)
    assert len(res.regions) == 0, f"Expected 0 false detections on background, got {len(res.regions)}"


def test_dual_yolo_bbox_accuracy():
    """Verify Dual YOLO detector produces accurate bounding boxes (not corrupt 0, 2, 21, 36)."""
    detector = DualYOLODetector(
        model_a_path="weights/model_a.pt",
        model_b_path="weights/model_b.pt",
        confidence_threshold=0.25,
    )
    test_img_path = "ml/data/drishti/test/images/synth_ghost_net_00001.png"
    img = cv2.imread(test_img_path)
    assert img is not None
    h0, w0 = img.shape[:2]

    res = detector.predict(img)
    assert len(res.regions) >= 1
    region = res.regions[0]
    x, y, w, h = region.bbox

    # Crucial check: box must NOT be the corrupted (0, 2, 21, 36) from the old buggy loop
    assert x > 50, f"BBox x={x} is corrupt; should be > 50"
    assert y > 100, f"BBox y={y} is corrupt; should be > 100"
    assert w > 30
    assert h > 30
    assert x + w <= w0
    assert y + h <= h0


def test_hybrid_detector():
    """Verify HybridAnomalyDetector ensemble combines UNet and YOLO."""
    detector = HybridAnomalyDetector(
        unet_model_path="ml/best_unet.pth",
        unet_threshold=0.5,
        yolo_a_path="weights/model_a.pt",
        yolo_b_path="weights/model_b.pt",
        yolo_threshold=0.25,
    )
    img = cv2.imread("ml/data/drishti/test/images/synth_ghost_net_00001.png")
    assert img is not None

    res = detector.predict(img)
    assert len(res.regions) >= 1
    assert res.processing_metadata["detector"] == "HybridAnomalyDetector"


def test_api_analyze_with_unet_backend(client: TestClient):
    """Verify /api/detections/analyze works end-to-end with detector_backend=unet."""
    test_img_path = "ml/data/drishti/test/images/synth_ghost_net_00001.png"
    with open(test_img_path, "rb") as f:
        img_bytes = f.read()

    files = {"file": ("synth_net.png", img_bytes, "image/png")}
    data = {
        "detector_backend": "unet",
        "latitude": "15.485123",
        "longitude": "73.801245",
        "heading": "45.0",
        "resolution": "0.15",
        "nadir_column": "100",
        "swath_channel": "starboard",
        "enable_visual_debug": "true",
    }

    res = client.post("/api/detections/analyze", files=files, data=data)
    assert res.status_code == 201
    payload = res.json()

    assert payload["detector_used"] == "UNetAnomalyDetector"
    assert payload["total_detections"] >= 1

    det = payload["detections"][0]
    assert det["anomaly_score"] >= 0.5
    assert det["priority"] in ("LOW", "MEDIUM", "HIGH")
    assert len(det["bbox"]) == 4

    x, y, w, h = det["bbox"]
    assert x > 50 and y > 100, f"API returned invalid bbox coordinates: {det['bbox']}"

    # Verify debug image was generated
    assert det["debug_image_path"] is not None
    assert os.path.exists(det["debug_image_path"])


def test_api_batch_with_unet_backend(client: TestClient):
    """Verify /api/detections/batch works end-to-end with detector_backend=unet."""
    path1 = "ml/data/drishti/test/images/synth_ghost_net_00001.png"
    path2 = "ml/data/drishti/test/images/bg_1693569243.750_x2500.jpg"

    with open(path1, "rb") as f1, open(path2, "rb") as f2:
        files = [
            ("files", ("net.png", f1.read(), "image/png")),
            ("files", ("bg.jpg", f2.read(), "image/jpeg")),
        ]

    data = {
        "detector_backend": "unet",
        "enable_visual_debug": "true",
    }

    res = client.post("/api/detections/batch", files=files, data=data)
    assert res.status_code == 201
    payload = res.json()

    assert payload["total_images"] == 2
    # Verify the net image has detections while bg has 0
    net_result = next(r for r in payload["results"] if r["filename"] == "net.png")
    bg_result = next(r for r in payload["results"] if r["filename"] == "bg.jpg")

    assert net_result["total_detections"] >= 1
    assert bg_result["total_detections"] == 0
    assert net_result["detections"][0]["bbox"][0] > 50


def test_anomaly_confidence_threshold_filtering(client: TestClient):
    """Verify that candidate regions with confidence <= 50% are skipped, and only > 50% are retained as anomalies."""
    # 1. Clean seafloor background image -> must yield 0 detections
    bg_path = "ml/data/drishti/test/images/bg_1693569243.750_x2500.jpg"
    with open(bg_path, "rb") as f:
        bg_bytes = f.read()

    res_bg = client.post(
        "/api/detections/analyze",
        files={"file": ("clean_seabed.jpg", bg_bytes, "image/jpeg")},
        data={"detector_backend": "unet"},
    )
    assert res_bg.status_code == 201
    bg_data = res_bg.json()
    assert bg_data["total_detections"] == 0
    assert bg_data["detections"] == []

    # 2. Ghost net target image -> must yield detections all strictly > 50% confidence
    net_path = "ml/data/drishti/test/images/synth_ghost_net_00001.png"
    with open(net_path, "rb") as f:
        net_bytes = f.read()

    res_net = client.post(
        "/api/detections/analyze",
        files={"file": ("synth_net.png", net_bytes, "image/png")},
        data={"detector_backend": "unet"},
    )
    assert res_net.status_code == 201
    net_data = res_net.json()
    assert net_data["total_detections"] >= 1
    for d in net_data["detections"]:
        assert d["confidence_percentage"] > 50.0, f"Detection {d['region_id']} confidence {d['confidence_percentage']} <= 50.0%"
        assert d["priority"] in ("HIGH", "MEDIUM")

    # 3. Mock detector test: mock_region_01 (>50%) is retained while mock_region_02 (<=50%) is skipped
    res_mock = client.post(
        "/api/detections/analyze",
        files={"file": ("synth_net.png", net_bytes, "image/png")},
        data={"detector_backend": "mock"},
    )
    assert res_mock.status_code == 201
    mock_data = res_mock.json()
    # Mock detector emits 2 candidate regions (01 and 02). 01 has >50% confidence, 02 has ~39.9% (<50%).
    # So exactly 1 anomaly must be returned!
    assert mock_data["total_detections"] == 1
    assert mock_data["detections"][0]["region_id"] == "mock_region_01"
    assert mock_data["detections"][0]["confidence_percentage"] > 50.0

