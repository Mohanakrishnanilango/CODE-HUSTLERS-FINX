import json
import math
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from pydantic import BaseModel, Field

from app.core.logging import logger

WGS84_R = 6371000.0  # Earth mean radius in meters


class TelemetryRecord(BaseModel):
    """Normalized telemetry information extracted from a JSON record."""
    source_file: Optional[str] = Field(default=None, description="Original JSON filename")
    image_name: Optional[str] = Field(default=None, description="Associated image name if specified in JSON")
    timestamp: Optional[str] = Field(default=None, description="Canonical ISO 8601 UTC timestamp")
    raw_timestamp: Optional[str] = Field(default=None, description="Original timestamp string from JSON")
    latitude: Optional[float] = Field(default=None, description="WGS84 latitude in decimal degrees")
    longitude: Optional[float] = Field(default=None, description="WGS84 longitude in decimal degrees")
    heading_deg: Optional[float] = Field(default=None, description="Heading in degrees from true North")
    altitude_m: Optional[float] = Field(default=None, description="Towfish altitude above seabed in meters")
    resolution_m_per_pixel: Optional[float] = Field(default=None, description="Resolution in meters per pixel")
    nadir_column: Optional[int] = Field(default=None, description="Nadir pixel column")
    swath_channel: Optional[str] = Field(default=None, description="'port', 'starboard', or 'both'")
    sonar_range_m: Optional[float] = Field(default=None, description="Sonar range in meters")
    target_class: Optional[str] = Field(default=None, description="Target object classification if annotated")
    confidence: Optional[float] = Field(default=None, description="Prior confidence if annotated")
    bbox: Optional[List[int]] = Field(default=None, description="Annotated bbox [x, y, w, h]")
    extra: Dict[str, Any] = Field(default_factory=dict, description="Any additional metadata fields")


class MatchResult(BaseModel):
    """Result of pairing an image with telemetry."""
    matched: bool
    matched_by: Optional[str] = Field(default=None, description="'filename', 'timestamp', or 'record_content'")
    image_filename: str
    json_filename: Optional[str] = None
    telemetry: Optional[TelemetryRecord] = None
    reason: Optional[str] = None


def normalize_timestamp(val: Any) -> Optional[str]:
    """
    Normalizes various timestamp formats into a canonical ISO8601 string: YYYY-MM-DDTHH:MM:SSZ
    Supports ISO formats, compact datetime (YYYYMMDD_HHMMSS), unix epochs, etc.
    """
    if val is None:
        return None

    if isinstance(val, (int, float)):
        # Possible epoch timestamp in seconds or milliseconds
        ts = float(val)
        if ts > 1e11:  # Milliseconds
            ts /= 1000.0
        try:
            dt = datetime.fromtimestamp(ts, tz=timezone.utc)
            return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        except Exception:
            return None

    s = str(val).strip()
    if not s:
        return None

    # Replace dashes/underscores in time part if needed
    # Try direct ISO parse
    clean_iso = s.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(clean_iso)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        pass

    # Patterns for YYYYMMDD_HHMMSS or YYYY-MM-DD HH:MM:SS or YYYY-MM-DD_HH-MM-SS
    patterns = [
        (r"^(\d{4})[-_]?(\d{2})[-_]?(\d{2})[T_\s](\d{2})[-_:]?(\d{2})[-_:]?(\d{2})$", "%Y%m%d%H%M%S"),
        (r"^(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})$", "%Y%m%d%H%M%S"),
        (r"^(\d{4})-(\d{2})-(\d{2})[T\s](\d{2}):(\d{2}):(\d{2})$", "%Y-%m-%d %H:%M:%S"),
        (r"^(\d{4})-(\d{2})-(\d{2})$", "%Y-%m-%d"),
    ]

    for regex, _ in patterns:
        m = re.match(regex, s)
        if m:
            groups = m.groups()
            if len(groups) == 6:
                y, mo, d, h, mi, sec = [int(g) for g in groups]
                try:
                    dt = datetime(y, mo, d, h, mi, sec, tzinfo=timezone.utc)
                    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
                except ValueError:
                    pass
            elif len(groups) == 3:
                y, mo, d = [int(g) for g in groups]
                try:
                    dt = datetime(y, mo, d, 0, 0, 0, tzinfo=timezone.utc)
                    return dt.strftime("%Y-%m-%dT00:00:00Z")
                except ValueError:
                    pass

    return s


def extract_timestamp_from_filename(filename: str) -> Optional[str]:
    """
    Extracts embedded date/time or epoch timestamp from a filename.
    Examples:
      - survey_2026-09-23T09_30_01Z.png -> 2026-09-23T09:30:01Z
      - sss_20260923_093001.png -> 2026-09-23T09:30:01Z
      - ping_1790155801.png -> converted epoch
    """
    base = Path(filename).stem

    # ISO-like pattern with T
    m_iso = re.search(r"(\d{4}-\d{2}-\d{2}[T_\s]\d{2}[-_:]?\d{2}[-_:]?\d{2}(?:\.\d+)?Z?)", base, re.IGNORECASE)
    if m_iso:
        ts = normalize_timestamp(m_iso.group(1))
        if ts:
            return ts

    # Compact pattern: YYYYMMDD_HHMMSS or YYYYMMDD-HHMMSS
    m_compact = re.search(r"(\d{4}\d{2}\d{2}[-_]\d{2}\d{2}\d{2})", base)
    if m_compact:
        raw = m_compact.group(1).replace("-", "_")
        ts = normalize_timestamp(raw)
        if ts:
            return ts

    # Epoch pattern (10 digits starting with 1 or 2)
    m_epoch = re.search(r"(?:^|_)((?:1|2)\d{9})(?:$|_)", base)
    if m_epoch:
        try:
            return normalize_timestamp(int(m_epoch.group(1)))
        except Exception:
            pass

    return None


def find_value_in_dict_recursive(d: Any, keys: List[str], max_depth: int = 4) -> Any:
    """Finds a key in nested dictionaries with priority to shallower depths and key order."""
    if not isinstance(d, dict) or max_depth <= 0:
        return None
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    # Check prioritized sub-dictionaries first
    priority_containers = ["navigation", "nav", "sonar", "telemetry", "gps", "location", "position", "properties", "vehicle", "auv"]
    for cont in priority_containers:
        if cont in d and isinstance(d[cont], dict):
            found = find_value_in_dict_recursive(d[cont], keys, max_depth=max_depth - 1)
            if found is not None:
                return found
    # Check remaining dictionaries
    for k, v in d.items():
        if k not in priority_containers and isinstance(v, dict):
            found = find_value_in_dict_recursive(v, keys, max_depth=max_depth - 1)
            if found is not None:
                return found
    return None


def extract_coordinates_from_dict(d: Dict[str, Any], max_depth: int = 4) -> Tuple[Optional[float], Optional[float]]:
    """
    Finds and extracts latitude and longitude from arbitrary nested dictionary structures.
    Supports:
      - lat / lon / latitude / longitude / lng / lat_deg / lon_deg
      - navigation: { latitude, longitude, ... } (AUV / Sonar formats)
      - coordinates: [lon, lat] (GeoJSON) or [lat, lon]
      - location: { lat, lon }
      - gps / position / telemetry / geometry
    """
    if not isinstance(d, dict) or max_depth <= 0:
        return None, None

    lat: Optional[float] = None
    lon: Optional[float] = None

    # 1. Direct top-level keys
    lat_keys = ["latitude", "lat", "survey_latitude", "survey_lat", "lat_deg", "lat_dd", "y"]
    lon_keys = ["longitude", "lon", "lng", "survey_longitude", "survey_lon", "lon_deg", "lon_dd", "x"]

    for k in lat_keys:
        if k in d and d[k] is not None:
            try:
                lat = float(d[k])
                break
            except (ValueError, TypeError):
                pass

    for k in lon_keys:
        if k in d and d[k] is not None:
            try:
                lon = float(d[k])
                break
            except (ValueError, TypeError):
                pass

    if lat is not None and lon is not None:
        return lat, lon

    # 2. Check prioritized nested containers (including navigation, nav, gps, location, etc.)
    nested_containers = [
        "navigation", "nav", "coordinates", "location", "position",
        "gps", "geometry", "telemetry", "coords", "properties",
        "vehicle", "auv", "state", "survey"
    ]
    for cont_key in nested_containers:
        if cont_key in d and isinstance(d[cont_key], dict):
            sub_lat, sub_lon = extract_coordinates_from_dict(d[cont_key], max_depth=max_depth - 1)
            if sub_lat is not None and sub_lon is not None:
                return sub_lat, sub_lon

    # 3. Check array coordinates (e.g. coordinates: [79.8136, 10.7623] or [10.7623, 79.8136])
    for arr_key in ["coordinates", "location", "position", "coords"]:
        if arr_key in d and isinstance(d[arr_key], (list, tuple)) and len(d[arr_key]) >= 2:
            try:
                v1 = float(d[arr_key][0])
                v2 = float(d[arr_key][1])
                is_geojson = (
                    d.get("type") in ["Feature", "Point"]
                    or "geometry" in d
                    or arr_key == "coordinates"
                )
                if is_geojson:
                    if -180.0 <= v1 <= 180.0 and -90.0 <= v2 <= 90.0:
                        return v2, v1
                if abs(v1) > 90 and abs(v2) <= 90:
                    return v2, v1
                elif abs(v2) > 90 and abs(v1) <= 90:
                    return v1, v2
                else:
                    return v1, v2
            except (ValueError, TypeError):
                pass

    # 4. Check any remaining dictionary children recursively
    for k, v in d.items():
        if k not in nested_containers and isinstance(v, dict):
            sub_lat, sub_lon = extract_coordinates_from_dict(v, max_depth=max_depth - 1)
            if sub_lat is not None and sub_lon is not None:
                return sub_lat, sub_lon

    return lat, lon


def parse_telemetry_dict(data: Dict[str, Any], source_file: Optional[str] = None) -> TelemetryRecord:
    """Parses a dictionary into a normalized TelemetryRecord."""
    lat, lon = extract_coordinates_from_dict(data)

    # Image name extraction
    img_name = None
    raw_img = find_value_in_dict_recursive(data, ["image", "image_id", "filename", "file_name", "image_name", "file", "img", "name", "ping_id"])
    if raw_img and isinstance(raw_img, str):
        img_name = Path(raw_img).name

    # Timestamp extraction
    raw_ts = find_value_in_dict_recursive(data, ["timestamp", "timestamp_utc", "acquisition_timestamp", "time", "time_utc", "datetime", "date_time", "date", "ping_time"])
    if raw_ts is not None:
        raw_ts = str(raw_ts)
    norm_ts = normalize_timestamp(raw_ts)

    # Heading
    heading: Optional[float] = None
    raw_heading = find_value_in_dict_recursive(data, ["heading_deg", "heading", "course", "bearing", "yaw"])
    if raw_heading is not None:
        try:
            heading = float(raw_heading)
        except (ValueError, TypeError):
            pass

    # Altitude
    altitude: Optional[float] = None
    raw_alt = find_value_in_dict_recursive(data, ["altitude_m", "altitude", "height_m", "towfish_altitude", "depth_m", "depth"])
    if raw_alt is not None:
        try:
            altitude = float(raw_alt)
        except (ValueError, TypeError):
            pass

    # Nadir Column
    nadir: Optional[int] = None
    raw_nadir = find_value_in_dict_recursive(data, ["nadir_column", "nadir_col", "nadir_x_px", "nadir_x", "nadir", "nadir_pixel"])
    if raw_nadir is not None:
        try:
            nadir = int(raw_nadir)
        except (ValueError, TypeError):
            pass

    # Sonar Range
    sonar_range: Optional[float] = None
    raw_range = find_value_in_dict_recursive(data, ["range_per_side_m", "sonar_range", "range", "range_m", "slant_range_m", "max_range_m"])
    if raw_range is not None:
        try:
            sonar_range = float(raw_range)
        except (ValueError, TypeError):
            pass

    # Resolution
    res: Optional[float] = None
    raw_res = find_value_in_dict_recursive(data, ["resolution", "resolution_m_per_pixel", "m_per_pixel", "res", "spatial_resolution", "pixel_size_m"])
    if raw_res is not None:
        try:
            res = float(raw_res)
        except (ValueError, TypeError):
            pass
    # Calculate resolution if not explicitly provided but range and nadir/width are present
    if res is None and sonar_range is not None and nadir is not None and nadir > 0:
        res = round(sonar_range / nadir, 4)
    elif res is None and sonar_range is not None:
        raw_width = find_value_in_dict_recursive(data, ["image_width_px", "image_width", "width_px", "width"])
        if raw_width is not None:
            try:
                w_val = float(raw_width)
                if w_val > 0:
                    res = round(sonar_range / (w_val / 2.0), 4)
            except (ValueError, TypeError):
                pass

    # Swath Channel
    channel: Optional[str] = None
    raw_channel = find_value_in_dict_recursive(data, ["swath_channel", "channel", "side"])
    if raw_channel is not None:
        channel = str(raw_channel).lower()

    # Target class / classification
    target_class: Optional[str] = None
    raw_class = find_value_in_dict_recursive(data, ["target_class", "object_class", "class", "label", "category"])
    if raw_class is not None:
        target_class = str(raw_class)

    # Confidence
    confidence: Optional[float] = None
    raw_conf = find_value_in_dict_recursive(data, ["confidence", "score", "confidence_percentage"])
    if raw_conf is not None:
        try:
            c = float(raw_conf)
            if c > 1.0:
                c /= 100.0
            confidence = c
        except (ValueError, TypeError):
            pass

    # Bbox
    bbox: Optional[List[int]] = None
    raw_bbox = find_value_in_dict_recursive(data, ["bbox", "bounding_box", "box"])
    if isinstance(raw_bbox, (list, tuple)) and len(raw_bbox) == 4:
        try:
            bbox = [int(v) for v in raw_bbox]
        except (ValueError, TypeError):
            pass

    return TelemetryRecord(
        source_file=source_file,
        image_name=img_name,
        timestamp=norm_ts,
        raw_timestamp=raw_ts,
        latitude=lat,
        longitude=lon,
        heading_deg=heading,
        altitude_m=altitude,
        resolution_m_per_pixel=res,
        nadir_column=nadir,
        swath_channel=channel,
        sonar_range_m=sonar_range,
        target_class=target_class,
        confidence=confidence,
        bbox=bbox,
        extra=data,
    )


class TelemetryParser:
    """
    Parser and indexing engine for JSON telemetry files.
    Extracts individual records, lists, or GeoJSON features.
    """

    def __init__(self):
        self.records: List[TelemetryRecord] = []

    def load_json_content(self, content: Union[str, bytes], source_filename: Optional[str] = None) -> List[TelemetryRecord]:
        """Parses JSON content (str or bytes) and registers extracted telemetry records."""
        if isinstance(content, bytes):
            text = content.decode("utf-8", errors="replace")
        else:
            text = str(content)

        parsed_records: List[TelemetryRecord] = []
        try:
            data = json.loads(text)
        except Exception as e:
            logger.warning(f"Failed to parse JSON from {source_filename}: {e}")
            return parsed_records

        # Handle list of records
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    rec = parse_telemetry_dict(item, source_file=source_filename)
                    parsed_records.append(rec)

        # Handle dict / GeoJSON / wrapper objects
        elif isinstance(data, dict):
            # Check GeoJSON FeatureCollection
            if data.get("type") == "FeatureCollection" and isinstance(data.get("features"), list):
                for feat in data["features"]:
                    if isinstance(feat, dict):
                        props = feat.get("properties", {}) or {}
                        geom = feat.get("geometry", {}) or {}
                        merged = {**props, "geometry": geom}
                        rec = parse_telemetry_dict(merged, source_file=source_filename)
                        parsed_records.append(rec)
            # Check survey records array e.g. {"pings": [...]} or {"records": [...]} or {"surveys": [...]}
            elif any(k in data and isinstance(data[k], list) for k in ["pings", "records", "surveys", "waypoints", "items"]):
                for k in ["pings", "records", "surveys", "waypoints", "items"]:
                    if k in data and isinstance(data[k], list):
                        for item in data[k]:
                            if isinstance(item, dict):
                                rec = parse_telemetry_dict(item, source_file=source_filename)
                                parsed_records.append(rec)
            else:
                # Single object
                rec = parse_telemetry_dict(data, source_file=source_filename)
                parsed_records.append(rec)

        self.records.extend(parsed_records)
        return parsed_records


def clean_stem(filename: str) -> str:
    """Cleans file stem by removing common suffixes like _meta, -telemetry, etc."""
    stem = Path(filename).stem.lower()
    for suffix in ["_meta", "-meta", "_telemetry", "-telemetry", "_nav", "-nav", "_metadata", "-metadata", "_gps"]:
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
            break
    return stem


def match_image_with_json(
    image_filename: str,
    telemetry_records: List[TelemetryRecord],
    image_timestamp: Optional[str] = None,
) -> MatchResult:
    """
    Pairs an image with the best matching TelemetryRecord according to:
    1. Exact or cleaned filename match (image name == JSON file stem or record's image_name property)
    2. Timestamp match (timestamp in image filename/parameter matches timestamp in JSON record)
    """
    img_name_clean = Path(image_filename).name.lower()
    img_stem_clean = clean_stem(image_filename)

    # 1. Match by Record's internal image_name property
    for rec in telemetry_records:
        if rec.image_name:
            rec_img_clean = Path(rec.image_name).name.lower()
            rec_stem_clean = clean_stem(rec.image_name)
            if img_name_clean == rec_img_clean or img_stem_clean == rec_stem_clean:
                return MatchResult(
                    matched=True,
                    matched_by="record_content",
                    image_filename=image_filename,
                    json_filename=rec.source_file,
                    telemetry=rec,
                    reason=f"Matched record image name '{rec.image_name}' to '{image_filename}'",
                )

    # 2. Match by JSON source file stem
    for rec in telemetry_records:
        if rec.source_file:
            json_stem = clean_stem(rec.source_file)
            if img_stem_clean == json_stem:
                return MatchResult(
                    matched=True,
                    matched_by="filename",
                    image_filename=image_filename,
                    json_filename=rec.source_file,
                    telemetry=rec,
                    reason=f"Matched image stem '{img_stem_clean}' with JSON file stem '{json_stem}'",
                )

    # 3. Match by Timestamp
    # Try provided timestamp or extract from image filename
    target_ts = normalize_timestamp(image_timestamp) or extract_timestamp_from_filename(image_filename)

    if target_ts:
        for rec in telemetry_records:
            if rec.timestamp:
                rec_norm_ts = normalize_timestamp(rec.timestamp)
                if rec_norm_ts == target_ts:
                    return MatchResult(
                        matched=True,
                        matched_by="timestamp",
                        image_filename=image_filename,
                        json_filename=rec.source_file,
                        telemetry=rec,
                        reason=f"Matched timestamp '{target_ts}' between image and JSON record",
                    )
            # Also check if JSON source filename contains matching timestamp
            if rec.source_file:
                json_file_ts = extract_timestamp_from_filename(rec.source_file)
                if json_file_ts and json_file_ts == target_ts:
                    return MatchResult(
                        matched=True,
                        matched_by="timestamp",
                        image_filename=image_filename,
                        json_filename=rec.source_file,
                        telemetry=rec,
                        reason=f"Matched timestamp '{target_ts}' in image filename and JSON filename '{rec.source_file}'",
                    )

    return MatchResult(
        matched=False,
        image_filename=image_filename,
        reason="No matching JSON telemetry found by filename or timestamp",
    )


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculates great-circle distance between two points on Earth in meters."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return WGS84_R * c


def initial_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculates forward azimuth / bearing in degrees (0-360) from point 1 to point 2."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_lambda = math.radians(lon2 - lon1)

    y = math.sin(delta_lambda) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(delta_lambda)
    theta = math.atan2(y, x)
    return (math.degrees(theta) + 360.0) % 360.0


def build_survey_route(
    waypoints_data: List[Dict[str, Any]]
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Builds an ordered survey route from a list of waypoint dictionaries.
    Sorts waypoints chronologically by timestamp (or ping index/original sequence).
    Calculates cumulative route distances and summary metrics.
    """
    if not waypoints_data:
        return [], {
            "total_waypoints": 0,
            "total_distance_m": 0.0,
            "total_distance_km": 0.0,
            "start_time": None,
            "end_time": None,
            "start_coordinates": None,
            "end_coordinates": None,
        }

    # Sort key: use timestamp if available, else original order
    def sort_key(item: Dict[str, Any]) -> str:
        ts = item.get("timestamp")
        if ts:
            return str(ts)
        return str(item.get("waypoint_index", 0)).zfill(8)

    sorted_points = sorted(waypoints_data, key=sort_key)

    total_dist_m = 0.0
    enriched_waypoints: List[Dict[str, Any]] = []

    for i, pt in enumerate(sorted_points):
        lat = float(pt["latitude"])
        lon = float(pt["longitude"])
        leg_dist = 0.0
        bearing = pt.get("heading")

        if i > 0:
            prev = sorted_points[i - 1]
            prev_lat = float(prev["latitude"])
            prev_lon = float(prev["longitude"])
            leg_dist = haversine_distance(prev_lat, prev_lon, lat, lon)
            total_dist_m += leg_dist
            if bearing is None:
                bearing = initial_bearing(prev_lat, prev_lon, lat, lon)

        wpt_entry = {
            **pt,
            "waypoint_index": i + 1,
            "latitude": lat,
            "longitude": lon,
            "heading": round(bearing, 1) if bearing is not None else None,
            "leg_distance_m": round(leg_dist, 2),
            "cumulative_distance_m": round(total_dist_m, 2),
        }
        enriched_waypoints.append(wpt_entry)

    first = enriched_waypoints[0]
    last = enriched_waypoints[-1]

    summary = {
        "total_waypoints": len(enriched_waypoints),
        "total_distance_m": round(total_dist_m, 2),
        "total_distance_km": round(total_dist_m / 1000.0, 3),
        "start_time": first.get("timestamp"),
        "end_time": last.get("timestamp"),
        "start_coordinates": (first["latitude"], first["longitude"]),
        "end_coordinates": (last["latitude"], last["longitude"]),
    }

    return enriched_waypoints, summary
