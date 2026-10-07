import math
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

from app.core.logging import logger
from app.schemas.survey import SurveyMetadata

WGS84_A = 6378137.0  # Earth equatorial radius in meters


class GeolocationResult(BaseModel):
    """
    Structured outcome of the geographic coordinate calculation.
    Guarantees no fabricated coordinates when metadata is incomplete.
    """
    available: bool = Field(..., description="True if valid WGS84 coordinates were calculated")
    latitude: Optional[float] = Field(default=None, description="Calculated WGS84 latitude")
    longitude: Optional[float] = Field(default=None, description="Calculated WGS84 longitude")
    reason: Optional[str] = Field(default=None, description="Explanation if coordinates could not be computed")
    coordinate_assumptions: Dict[str, Any] = Field(
        default_factory=dict,
        description="Assumptions, references, and coordinate frames used in calculation"
    )


def calculate_anomaly_geolocation(
    anomaly_centroid: Tuple[float, float],
    image_shape: Tuple[int, int],
    metadata: Optional[SurveyMetadata],
) -> GeolocationResult:
    """
    Transforms pixel coordinates of an anomaly into geographic WGS84 coordinates (latitude, longitude)
    using side-scan sonar geometry and dead-reckoning geodesy.

    Acoustic Geometry Assumptions:
    1. Coordinate Frame: Image (row, col) maps to (along-track, across-track).
       - Along-track (row axis): row 0 is top of image, row H-1 is bottom.
         Center row H/2 corresponds to the sensor position at the nominal survey coordinate.
       - Across-track (col axis): col 0 is port-most pixel (or nadir if single channel).
         Column nadir_column corresponds to acoustic nadir (zero across-track offset).
    2. Heading Rotation: Heading theta is measured in degrees clockwise from true North.
       - Along-track unit vector = (sin(theta), cos(theta)) in (East, North)
       - Across-track starboard unit vector = (cos(theta), -sin(theta)) in (East, North)
    3. Ellipsoid: WGS84 mean spherical radius R = 6,378,137.0 m for local tangent plane offset.

    CRITICAL RULE:
    If any essential metadata is missing, returns available=False with latitude=None, longitude=None.
    Never fabricates coordinates.
    """
    missing_fields: List[str] = []

    if metadata is None:
        return GeolocationResult(
            available=False,
            latitude=None,
            longitude=None,
            reason="Survey metadata object is completely absent.",
        )

    if metadata.survey_latitude is None:
        missing_fields.append("survey_latitude")
    if metadata.survey_longitude is None:
        missing_fields.append("survey_longitude")
    if metadata.resolution_m_per_pixel is None or metadata.resolution_m_per_pixel <= 0:
        missing_fields.append("resolution_m_per_pixel")
    if metadata.heading_deg is None:
        missing_fields.append("heading_deg")

    if missing_fields:
        return GeolocationResult(
            available=False,
            latitude=None,
            longitude=None,
            reason=f"Insufficient metadata for geographic projection; missing: {missing_fields}",
            coordinate_assumptions={"missing_parameters": missing_fields},
        )

    cx, cy = anomaly_centroid
    img_h, img_w = image_shape
    res = metadata.resolution_m_per_pixel
    lat_0 = metadata.survey_latitude
    lon_0 = metadata.survey_longitude
    heading_rad = math.radians(metadata.heading_deg)

    # Determine nadir column
    nadir_col = metadata.nadir_column if metadata.nadir_column is not None else (img_w / 2.0)

    # Offset in meters relative to sensor track center
    # Across-track: positive = starboard (right of nadir), negative = port (left of nadir)
    d_across = (cx - nadir_col) * res

    # Along-track: positive = ahead of ping center, negative = behind ping center
    d_along = (cy - (img_h / 2.0)) * res

    # Rotate into East, North offsets
    # Along track points along heading vector (sin theta, cos theta)
    # Starboard across track points perpendicular (cos theta, -sin theta)
    delta_east = d_along * math.sin(heading_rad) + d_across * math.cos(heading_rad)
    delta_north = d_along * math.cos(heading_rad) - d_across * math.sin(heading_rad)

    # Convert meter offsets to delta latitude & delta longitude on WGS84
    # 1 deg lat ~ 111,320 m
    # 1 deg lon ~ 111,320 m * cos(lat)
    delta_lat = (delta_north / WGS84_A) * (180.0 / math.pi)
    lat_rad = math.radians(lat_0)
    cos_lat = math.cos(lat_rad)
    if abs(cos_lat) < 1e-6:
        cos_lat = 1e-6  # Guard against polar singularities

    delta_lon = (delta_east / (WGS84_A * cos_lat)) * (180.0 / math.pi)

    target_lat = lat_0 + delta_lat
    target_lon = lon_0 + delta_lon

    # Validate coordinate range
    if not (-90.0 <= target_lat <= 90.0 and -180.0 <= target_lon <= 180.0):
        return GeolocationResult(
            available=False,
            latitude=None,
            longitude=None,
            reason=f"Calculated coordinates ({target_lat:.6f}, {target_lon:.6f}) fell outside valid WGS84 bounds.",
        )

    return GeolocationResult(
        available=True,
        latitude=round(target_lat, 7),
        longitude=round(target_lon, 7),
        reason=None,
        coordinate_assumptions={
            "datum": "WGS84",
            "projection": "Local tangent geodesic dead-reckoning",
            "survey_origin": [lat_0, lon_0],
            "heading_deg": metadata.heading_deg,
            "resolution_m_per_px": res,
            "nadir_column_used": nadir_col,
            "offset_meters": {
                "across_track_m": round(d_across, 2),
                "along_track_m": round(d_along, 2),
                "delta_east_m": round(delta_east, 2),
                "delta_north_m": round(delta_north, 2),
            },
        },
    )
