import json
import pytest
from app.services.telemetry.parser import (
    TelemetryParser,
    clean_stem,
    extract_timestamp_from_filename,
    extract_coordinates_from_dict,
    haversine_distance,
    match_image_with_json,
    normalize_timestamp,
    build_survey_route,
)


def test_timestamp_normalization():
    assert normalize_timestamp("2026-09-23T09:30:01Z") == "2026-09-23T09:30:01Z"
    assert normalize_timestamp("20260923_093001") == "2026-09-23T09:30:01Z"
    assert normalize_timestamp("2026-09-23 09:30:01") == "2026-09-23T09:30:01Z"


def test_extract_timestamp_from_filename():
    assert extract_timestamp_from_filename("ping_20260923_093001.png") == "2026-09-23T09:30:01Z"
    assert extract_timestamp_from_filename("survey_2026-09-23T09:30:01Z.tif") == "2026-09-23T09:30:01Z"


def test_extract_coordinates():
    # Flat
    assert extract_coordinates_from_dict({"latitude": 9.952, "longitude": 76.125}) == (9.952, 76.125)
    assert extract_coordinates_from_dict({"lat": 9.952, "lon": 76.125}) == (9.952, 76.125)
    # GeoJSON coordinates [lon, lat]
    assert extract_coordinates_from_dict({"type": "Point", "coordinates": [76.125, 9.952]}) == (9.952, 76.125)
    # Nested location
    assert extract_coordinates_from_dict({"location": {"latitude": 9.952, "longitude": 76.125}}) == (9.952, 76.125)


def test_matching_by_filename():
    parser = TelemetryParser()
    json_bytes = json.dumps({
        "latitude": 9.9520,
        "longitude": 76.1250,
        "heading": 82.8,
        "timestamp": "2026-09-23T09:30:01Z"
    }).encode("utf-8")
    records = parser.load_json_content(json_bytes, source_filename="ping_0001.json")

    # Image with matching stem
    res = match_image_with_json("ping_0001.png", records)
    assert res.matched is True
    assert res.matched_by == "filename"
    assert res.telemetry.latitude == 9.9520
    assert res.telemetry.longitude == 76.1250


def test_matching_by_timestamp():
    parser = TelemetryParser()
    json_bytes = json.dumps({
        "latitude": 15.485,
        "longitude": 73.801,
        "timestamp": "2026-09-24T12:00:00Z"
    }).encode("utf-8")
    # Different filename, but timestamp matches
    records = parser.load_json_content(json_bytes, source_filename="nav_data_log.json")

    res = match_image_with_json("sss_image_20260924_120000.png", records)
    assert res.matched is True
    assert res.matched_by == "timestamp"
    assert res.telemetry.latitude == 15.485
    assert res.telemetry.longitude == 73.801


def test_matching_by_record_image_name():
    parser = TelemetryParser()
    json_bytes = json.dumps({
        "image": "custom_sonar.png",
        "latitude": 10.123,
        "longitude": 75.456,
        "timestamp": "2026-09-23T10:00:00Z"
    }).encode("utf-8")
    records = parser.load_json_content(json_bytes, source_filename="survey_list.json")

    res = match_image_with_json("custom_sonar.png", records)
    assert res.matched is True
    assert res.matched_by == "record_content"
    assert res.telemetry.latitude == 10.123


def test_build_survey_route():
    waypoints = [
        {"latitude": 9.9520, "longitude": 76.1250, "timestamp": "2026-09-23T09:30:01Z", "filename": "p1.png"},
        {"latitude": 9.9525, "longitude": 76.1257, "timestamp": "2026-09-23T09:30:02Z", "filename": "p2.png"},
        {"latitude": 9.9514, "longitude": 76.1244, "timestamp": "2026-09-23T09:30:03Z", "filename": "p3.png"},
    ]
    route, summary = build_survey_route(waypoints)
    assert len(route) == 3
    assert summary["total_waypoints"] == 3
    assert summary["total_distance_m"] > 0
    assert route[0]["waypoint_index"] == 1
    assert route[1]["waypoint_index"] == 2
    assert route[2]["waypoint_index"] == 3
    assert route[1]["leg_distance_m"] > 0
