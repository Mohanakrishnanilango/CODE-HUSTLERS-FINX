import io
import json
import pytest
from fastapi.testclient import TestClient


def test_analyze_image_with_json_file_matching_name(client: TestClient, sample_sss_image_bytes: bytes):
    """Test /api/detections/analyze with matching image and JSON file."""
    # JSON file with same stem 'ping_0001'
    json_content = json.dumps({
        "filename": "ping_0001.png",
        "latitude": 9.952000,
        "longitude": 76.125000,
        "heading": 82.8,
        "resolution": 0.1,
        "timestamp": "2026-09-23T09:30:01Z",
        "target_class": "ghost_net"
    }).encode("utf-8")

    files = {
        "file": ("ping_0001.png", sample_sss_image_bytes, "image/png"),
        "json_file": ("ping_0001.json", json_content, "application/json"),
    }
    response = client.post("/api/detections/analyze", files=files)
    assert response.status_code == 201
    data = response.json()
    assert data["filename"] == "ping_0001.png"
    assert data["survey_latitude"] == 9.952000
    assert data["survey_longitude"] == 76.125000
    assert data["matched_by"] in ["record_content", "filename", "single_upload"]
    assert data["route_point"] is not None
    assert data["route_point"]["latitude"] is not None
    assert data["route_point"]["longitude"] is not None


def test_analyze_image_with_json_file_matching_timestamp(client: TestClient, sample_sss_image_bytes: bytes):
    """Test /api/detections/analyze with matching timestamp between image and JSON file."""
    # Image name has timestamp 20260924_143000, JSON has different filename but same timestamp
    json_content = json.dumps({
        "latitude": 15.485120,
        "longitude": 73.801250,
        "heading": 45.0,
        "resolution": 0.1,
        "timestamp": "2026-09-24T14:30:00Z"
    }).encode("utf-8")

    files = {
        "file": ("sonar_20260924_143000.png", sample_sss_image_bytes, "image/png"),
        "json_file": ("navigation_log.json", json_content, "application/json"),
    }
    response = client.post("/api/detections/analyze", files=files)
    assert response.status_code == 201
    data = response.json()
    assert data["survey_latitude"] == 15.485120
    assert data["survey_longitude"] == 73.801250
    assert data["matched_by"] == "timestamp"


def test_batch_analyze_with_image_and_json_pairs_making_route(client: TestClient, sample_sss_image_bytes: bytes):
    """Test /api/detections/batch with multiple images and JSON files creating an ordered route."""
    # Create 3 ping image bytes and 3 JSON files
    p1_json = json.dumps({
        "latitude": 9.952000,
        "longitude": 76.125000,
        "heading": 82.8,
        "timestamp": "2026-09-23T09:30:01Z"
    }).encode("utf-8")

    p2_json = json.dumps({
        "latitude": 9.952500,
        "longitude": 76.125700,
        "heading": 83.1,
        "timestamp": "2026-09-23T09:30:02Z"
    }).encode("utf-8")

    p3_json = json.dumps({
        "latitude": 9.951400,
        "longitude": 76.124400,
        "heading": 82.5,
        "timestamp": "2026-09-23T09:30:03Z"
    }).encode("utf-8")

    files = [
        ("files", ("ping_0001.png", sample_sss_image_bytes, "image/png")),
        ("files", ("ping_0001.json", p1_json, "application/json")),
        ("files", ("ping_0002.png", sample_sss_image_bytes, "image/png")),
        ("files", ("ping_0002.json", p2_json, "application/json")),
        ("files", ("ping_0003.png", sample_sss_image_bytes, "image/png")),
        ("files", ("ping_0003.json", p3_json, "application/json")),
    ]

    response = client.post("/api/detections/batch", files=files)
    assert response.status_code == 201
    data = response.json()
    assert data["total_images"] == 3
    assert data["processed"] == 3
    assert len(data["route"]) == 3
    assert data["route_summary"] is not None
    assert data["route_summary"]["total_waypoints"] == 3
    assert data["route_summary"]["total_distance_m"] > 0
    # Verify order
    assert data["route"][0]["waypoint_index"] == 1
    assert data["route"][1]["waypoint_index"] == 2
    assert data["route"][2]["waypoint_index"] == 3
    # Check that each result has coordinates
    for res in data["results"]:
        assert res["survey_latitude"] is not None
        assert res["survey_longitude"] is not None
        assert res["matched_by"] == "filename"


def test_single_image_json_overrides_manual_gps(client: TestClient, sample_sss_image_bytes: bytes):
    """Verify that JSON file latitude/longitude strictly takes precedence over manual form coordinates."""
    json_content = json.dumps({
        "latitude": 9.952000,
        "longitude": 76.125000,
        "heading": 82.8,
        "resolution": 0.1,
    }).encode("utf-8")

    files = {
        "file": ("test_sonar.png", sample_sss_image_bytes, "image/png"),
        "json_file": ("test_sonar.json", json_content, "application/json"),
    }
    # Even if manual latitude and longitude are submitted in form data:
    data_form = {
        "latitude": "15.485120",
        "longitude": "73.801250",
    }
    response = client.post("/api/detections/analyze", files=files, data=data_form)
    assert response.status_code == 201
    res = response.json()
    # Must use JSON latitude & longitude (9.952, 76.125), NOT manual form (15.48512, 73.80125)
    assert res["survey_latitude"] == 9.952000
    assert res["survey_longitude"] == 76.125000
    assert pytest.approx(res["route_point"]["latitude"], abs=1e-3) == 9.952000
    assert pytest.approx(res["route_point"]["longitude"], abs=1e-3) == 76.125000


def test_single_image_with_nested_coordinates_in_json(client: TestClient, sample_sss_image_bytes: bytes):
    """Verify extraction from nested location/gps dictionary in JSON file."""
    json_content = json.dumps({
        "location": {
            "latitude": 11.234567,
            "longitude": 75.890123
        },
        "heading": 120.0,
        "resolution": 0.15
    }).encode("utf-8")

    files = {
        "file": ("sonar_ping.png", sample_sss_image_bytes, "image/png"),
        "json_file": ("sonar_ping.json", json_content, "application/json"),
    }
    response = client.post("/api/detections/analyze", files=files)
    assert response.status_code == 201
    res = response.json()
    assert res["survey_latitude"] == 11.234567
    assert res["survey_longitude"] == 75.890123


def test_batch_image_json_overrides_manual_gps(client: TestClient, sample_sss_image_bytes: bytes):
    """Verify that in batch mode, JSON file coordinates override any form coordinates."""
    j1 = json.dumps({"latitude": 9.9520, "longitude": 76.1250}).encode("utf-8")
    j2 = json.dumps({"latitude": 9.9530, "longitude": 76.1260}).encode("utf-8")

    files = [
        ("files", ("p1.png", sample_sss_image_bytes, "image/png")),
        ("files", ("p1.json", j1, "application/json")),
        ("files", ("p2.png", sample_sss_image_bytes, "image/png")),
        ("files", ("p2.json", j2, "application/json")),
    ]
    data_form = {
        "latitude": "15.485120",
        "longitude": "73.801250",
    }
    response = client.post("/api/detections/batch", files=files, data=data_form)
    assert response.status_code == 201
    res = response.json()
    assert res["results"][0]["survey_latitude"] == 9.9520
    assert res["results"][0]["survey_longitude"] == 76.1250
    assert res["results"][1]["survey_latitude"] == 9.9530
    assert res["results"][1]["survey_longitude"] == 76.1260


def test_single_image_no_json_no_manual_gps_does_not_fabricate(client: TestClient, sample_sss_image_bytes: bytes):
    """Verify that if no JSON file is supplied and no manual GPS is sent, coordinates remain null without fabrication."""
    files = {
        "file": ("pure_sonar.png", sample_sss_image_bytes, "image/png"),
    }
    response = client.post("/api/detections/analyze", files=files)
    assert response.status_code == 201
    res = response.json()
    assert res["survey_latitude"] is None
    assert res["survey_longitude"] is None
    assert res["route_point"] is None
    for det in res["detections"]:
        assert det["geolocation"]["available"] is False
        assert det["geolocation"]["latitude"] is None
        assert det["geolocation"]["longitude"] is None


def test_single_image_auv_navigation_schema(client: TestClient, sample_sss_image_bytes: bytes):
    """
    Test single image upload with the exact user AUV telemetry JSON schema:
    - Latitude and longitude nested under 'navigation'
    - Sonar range and nadir nested under 'sonar'
    - Image matching by 'image_id'
    - Timestamp from 'timestamp_utc'
    """
    user_json = {
        "image_id": "sss_sample_001",
        "auv_id": "AUV-01",
        "timestamp_utc": "2026-09-21T10:24:17Z",
        "coordinate_system": "WGS84",
        "navigation": {
            "latitude": 10.7623,
            "longitude": 79.8136,
            "heading_deg": 142.6,
            "depth_m": 48.7,
            "altitude_m": 8.0,
            "speed_knots": 2.3,
        },
        "sonar": {
            "range_per_side_m": 100,
            "image_width_px": 1024,
            "image_height_px": 512,
            "nadir_x_px": 512,
        },
    }
    json_bytes = json.dumps(user_json).encode("utf-8")

    files = {
        "file": ("sss_sample_001.png", sample_sss_image_bytes, "image/png"),
        "json_file": ("auv_mission_log.json", json_bytes, "application/json"),
    }
    response = client.post("/api/detections/analyze", files=files)
    assert response.status_code == 201
    res = response.json()

    assert res["survey_latitude"] == 10.7623
    assert res["survey_longitude"] == 79.8136
    assert res["acquisition_timestamp"] == "2026-09-21T10:24:17Z"
    assert res["matched_by"] == "record_content"
    assert res["route_point"] is not None
    assert pytest.approx(res["route_point"]["latitude"], abs=1e-3) == 10.7623
    assert pytest.approx(res["route_point"]["longitude"], abs=1e-3) == 79.8136
    assert res["route_point"]["heading"] == 142.6
    assert res["route_point"]["altitude"] == 8.0


def test_batch_auv_navigation_schema(client: TestClient, sample_sss_image_bytes: bytes):
    """
    Test batch image upload with user AUV telemetry JSON schemas matching by image_id.
    """
    j1 = {
        "image_id": "sss_sample_001",
        "auv_id": "AUV-01",
        "timestamp_utc": "2026-09-21T10:24:17Z",
        "coordinate_system": "WGS84",
        "navigation": {
            "latitude": 10.7623,
            "longitude": 79.8136,
            "heading_deg": 142.6,
        },
        "sonar": {
            "range_per_side_m": 100,
            "nadir_x_px": 512,
        },
    }
    j2 = {
        "image_id": "sss_sample_002",
        "auv_id": "AUV-01",
        "timestamp_utc": "2026-09-21T10:25:17Z",
        "coordinate_system": "WGS84",
        "navigation": {
            "latitude": 10.7630,
            "longitude": 79.8145,
            "heading_deg": 143.0,
        },
        "sonar": {
            "range_per_side_m": 100,
            "nadir_x_px": 512,
        },
    }

    files = [
        ("files", ("sss_sample_001.png", sample_sss_image_bytes, "image/png")),
        ("files", ("auv_log_001.json", json.dumps(j1).encode("utf-8"), "application/json")),
        ("files", ("sss_sample_002.png", sample_sss_image_bytes, "image/png")),
        ("files", ("auv_log_002.json", json.dumps(j2).encode("utf-8"), "application/json")),
    ]

    response = client.post("/api/detections/batch", files=files)
    assert response.status_code == 201
    res = response.json()
    assert res["total_images"] == 2
    assert res["processed"] == 2

    # Verify both images matched and have coordinates from 'navigation'
    r1 = next(r for r in res["results"] if "sss_sample_001" in r["filename"])
    r2 = next(r for r in res["results"] if "sss_sample_002" in r["filename"])

    assert r1["survey_latitude"] == 10.7623
    assert r1["survey_longitude"] == 79.8136
    assert r2["survey_latitude"] == 10.7630
    assert r2["survey_longitude"] == 79.8145
    assert len(res["route"]) == 2
    assert pytest.approx(res["route"][0]["latitude"], abs=1e-3) == 10.7623
    assert pytest.approx(res["route"][1]["latitude"], abs=1e-3) == 10.7630


def test_batch_single_image_with_user_json(client: TestClient, sample_sss_image_bytes: bytes):
    """Test batch endpoint with 1 single image and 1 user AUV JSON file."""
    user_json = {
        "image_id": "sss_sample_001",
        "auv_id": "AUV-01",
        "timestamp_utc": "2026-09-21T10:24:17Z",
        "navigation": {
            "latitude": 10.7623,
            "longitude": 79.8136,
            "heading_deg": 142.6,
        },
        "sonar": {
            "range_per_side_m": 100,
        },
    }
    files = [
        ("files", ("sss_sample_001.png", sample_sss_image_bytes, "image/png")),
        ("files", ("telemetry.json", json.dumps(user_json).encode("utf-8"), "application/json")),
    ]
    response = client.post("/api/detections/batch", files=files)
    assert response.status_code == 201
    data = response.json()
    assert data["total_images"] == 1
    assert data["processed"] == 1
    assert len(data["results"]) == 1
    assert data["results"][0]["survey_latitude"] == 10.7623
    assert data["results"][0]["survey_longitude"] == 79.8136
    assert len(data["route"]) == 1
    assert data["route"][0]["latitude"] == 10.7623
    assert data["route_summary"] is not None
    assert data["route_summary"]["total_waypoints"] == 1


def test_batch_single_image_without_json(client: TestClient, sample_sss_image_bytes: bytes):
    """Test batch endpoint with 1 single image without JSON files (does not crash)."""
    files = [
        ("files", ("solo_sonar.png", sample_sss_image_bytes, "image/png")),
    ]
    response = client.post("/api/detections/batch", files=files)
    assert response.status_code == 201
    data = response.json()
    assert data["total_images"] == 1
    assert data["processed"] == 1
    assert len(data["results"]) == 1
    assert data["results"][0]["survey_latitude"] is None
    assert len(data["route"]) == 0


def test_batch_analyze_persists_images_and_serves_image_url(client: TestClient, sample_sss_image_bytes: bytes):
    """Verify that batch analysis commits images to DB and allows fetching original images via image_url."""
    files = [
        ("files", ("batch_ping_01.png", sample_sss_image_bytes, "image/png")),
        ("files", ("batch_ping_02.png", sample_sss_image_bytes, "image/png")),
    ]
    response = client.post("/api/detections/batch", files=files)
    assert response.status_code == 201
    data = response.json()
    assert data["total_images"] == 2

    for res_item in data["results"]:
        assert "image_url" in res_item
        assert res_item["image_url"] is not None
        assert f"/api/detections/images/{res_item['image_id']}" == res_item["image_url"]

        # Fetch original uploaded image through the API
        img_res = client.get(res_item["image_url"])
        assert img_res.status_code == 200
        assert len(img_res.content) > 0


def test_detection_original_image_endpoint(client: TestClient, sample_sss_image_bytes: bytes):
    """Verify that detection original image endpoint returns the original uploaded image."""
    files = {"file": ("test_flow.png", sample_sss_image_bytes, "image/png")}
    data = {"latitude": "15.0", "longitude": "75.0"}
    analyze_res = client.post("/api/detections/analyze", files=files, data=data)
    assert analyze_res.status_code == 201
    payload = analyze_res.json()
    assert "image_url" in payload
    det_id = payload["detections"][0]["detection_id"]

    # Test /api/detections/{detection_id}/original-image
    orig_res = client.get(f"/api/detections/{det_id}/original-image")
    assert orig_res.status_code == 200
    assert len(orig_res.content) > 0




