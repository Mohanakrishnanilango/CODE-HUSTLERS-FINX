import pytest
from app.schemas.survey import SurveyMetadata
from app.services.geolocation.calculator import calculate_anomaly_geolocation


def test_geolocation_complete_metadata():
    # Survey at (15.0, 75.0), heading North (0 deg), resolution 0.1 m/px, nadir at col 100
    metadata = SurveyMetadata(
        survey_latitude=15.0,
        survey_longitude=75.0,
        heading_deg=0.0,
        resolution_m_per_pixel=0.1,
        nadir_column=100,
    )

    # Anomaly at center (100, 100) on a 200x200 image -> zero offset
    res = calculate_anomaly_geolocation(
        anomaly_centroid=(100.0, 100.0),
        image_shape=(200, 200),
        metadata=metadata,
    )

    assert res.available is True
    assert res.latitude == pytest.approx(15.0, abs=1e-6)
    assert res.longitude == pytest.approx(75.0, abs=1e-6)

    # Anomaly 500 px starboard (col 600, row 100) with heading=90 (East)
    # Heading=90 -> along track is East, across track starboard is South
    metadata_east = SurveyMetadata(
        survey_latitude=15.0,
        survey_longitude=75.0,
        heading_deg=90.0,
        resolution_m_per_pixel=0.1,
        nadir_column=100,
    )
    res_offset = calculate_anomaly_geolocation(
        anomaly_centroid=(200.0, 100.0),  # 100 px starboard = 10 meters starboard
        image_shape=(200, 200),
        metadata=metadata_east,
    )
    assert res_offset.available is True
    assert res_offset.latitude < 15.0  # Starboard when heading East is South!


def test_geolocation_missing_latitude_no_fabrication():
    metadata = SurveyMetadata(
        survey_latitude=None,
        survey_longitude=75.0,
        heading_deg=0.0,
        resolution_m_per_pixel=0.1,
    )
    res = calculate_anomaly_geolocation((100.0, 100.0), (200, 200), metadata)
    assert res.available is False
    assert res.latitude is None
    assert res.longitude is None
    assert "survey_latitude" in res.reason


def test_geolocation_missing_resolution_no_fabrication():
    metadata = SurveyMetadata(
        survey_latitude=15.0,
        survey_longitude=75.0,
        heading_deg=0.0,
        resolution_m_per_pixel=None,
    )
    res = calculate_anomaly_geolocation((100.0, 100.0), (200, 200), metadata)
    assert res.available is False
    assert res.latitude is None
    assert res.longitude is None
    assert "resolution_m_per_pixel" in res.reason


def test_geolocation_missing_heading_no_fabrication():
    metadata = SurveyMetadata(
        survey_latitude=15.0,
        survey_longitude=75.0,
        heading_deg=None,
        resolution_m_per_pixel=0.1,
    )
    res = calculate_anomaly_geolocation((100.0, 100.0), (200, 200), metadata)
    assert res.available is False
    assert res.latitude is None
    assert res.longitude is None
    assert "heading_deg" in res.reason
