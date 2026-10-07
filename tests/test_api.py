import io
import pytest
from fastapi.testclient import TestClient


def test_root_and_health(client: TestClient):
    res = client.get("/")
    assert res.status_code == 200
    assert res.json()["status"] == "online"

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "healthy"


def test_analyze_with_complete_metadata(client: TestClient, sample_sss_image_bytes: bytes):
    files = {"file": ("test_sonar.png", sample_sss_image_bytes, "image/png")}
    data = {
        "latitude": "15.485123",
        "longitude": "73.801245",
        "heading": "45.0",
        "resolution": "0.15",
        "nadir_column": "100",
        "swath_channel": "both",
        "enable_visual_debug": "true",
    }

    res = client.post("/api/detections/analyze", files=files, data=data)
    assert res.status_code == 201
    payload = res.json()

    assert payload["total_detections"] >= 1
    assert payload["filename"] == "test_sonar.png"
    assert payload["detector_used"] == "MockAnomalyDetector"

    # Verify ranked order
    detections = payload["detections"]
    for i in range(len(detections) - 1):
        assert detections[i]["final_confidence"] >= detections[i + 1]["final_confidence"]
        assert detections[i]["rank"] == i + 1

    first = detections[0]
    assert first["final_confidence"] > 0.0
    assert first["priority"] in ("LOW", "MEDIUM", "HIGH")
    assert first["geolocation"]["available"] is True
    assert first["geolocation"]["latitude"] is not None
    assert first["geolocation"]["longitude"] is not None
    assert first["debug_image_path"] is not None


def test_analyze_with_missing_metadata_no_fabrication(client: TestClient, sample_sss_image_bytes: bytes):
    files = {"file": ("test_sonar_no_meta.png", sample_sss_image_bytes, "image/png")}
    # No survey latitude, longitude, heading, or resolution!
    data = {
        "enable_visual_debug": "false",
    }

    res = client.post("/api/detections/analyze", files=files, data=data)
    assert res.status_code == 201
    payload = res.json()

    detections = payload["detections"]
    assert len(detections) >= 1

    first = detections[0]
    # Geolocation must be unavailable and NEVER fabricated
    assert first["geolocation"]["available"] is False
    assert first["geolocation"]["latitude"] is None
    assert first["geolocation"]["longitude"] is None
    assert "missing" in first["geolocation"]["reason"].lower()

    # Evidence scores: size must be unavailable because resolution was missing
    assert first["evidence_scores"]["size"] is None


def test_analyze_invalid_corrupt_file(client: TestClient):
    files = {"file": ("corrupt.png", b"not a real image buffer", "image/png")}
    res = client.post("/api/detections/analyze", files=files)
    assert res.status_code in (400, 422)


def test_get_detection_endpoints(client: TestClient, sample_sss_image_bytes: bytes):
    # 1. First analyze an image to populate DB
    files = {"file": ("test_flow.png", sample_sss_image_bytes, "image/png")}
    data = {
        "latitude": "15.0",
        "longitude": "75.0",
        "heading": "0.0",
        "resolution": "0.10",
        "nadir_column": "100",
    }
    analyze_res = client.post("/api/detections/analyze", files=files, data=data)
    assert analyze_res.status_code == 201
    det_id = analyze_res.json()["detections"][0]["detection_id"]

    # 2. List all detections
    list_res = client.get("/api/detections")
    assert list_res.status_code == 200
    assert len(list_res.json()) >= 1

    # 3. Get single detection
    detail_res = client.get(f"/api/detections/{det_id}")
    assert detail_res.status_code == 200
    assert detail_res.json()["detection_id"] == det_id

    # 4. Get evidence breakdown
    ev_res = client.get(f"/api/detections/{det_id}/evidence")
    assert ev_res.status_code == 200
    ev_data = ev_res.json()
    assert "shape" in ev_data
    assert "texture" in ev_data
    assert "shadow" in ev_data
    assert "fusion_audit" in ev_data

    # 5. Get report (JSON)
    rep_json = client.get(f"/api/detections/{det_id}/report?format=json")
    assert rep_json.status_code == 200
    assert rep_json.json()["detection_id"] == det_id

    # 6. Get report (Markdown)
    rep_md = client.get(f"/api/detections/{det_id}/report?format=markdown")
    assert rep_md.status_code == 200
    assert "SSS Ghost Net Detection Audit Report" in rep_md.text

    # 7. Get debug image
    dbg_img = client.get(f"/api/detections/{det_id}/debug-image")
    assert dbg_img.status_code == 200
    assert dbg_img.headers["content-type"] == "image/png"
