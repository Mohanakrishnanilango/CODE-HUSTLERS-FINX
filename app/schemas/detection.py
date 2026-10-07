from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

from app.schemas.evidence import CompleteEvidenceSet, EvidenceResult
from app.services.evidence.fusion import FusionResult
from app.services.geolocation.calculator import GeolocationResult


class GeolocationSummary(BaseModel):
    available: bool
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    reason: Optional[str] = None


class EvidenceScoresSummary(BaseModel):
    shape: Optional[float] = None
    texture: Optional[float] = None
    shadow: Optional[float] = None
    size: Optional[float] = None
    context: Optional[float] = None


class DetectionResponseItem(BaseModel):
    detection_id: str
    region_id: str
    rank: int
    bbox: Tuple[int, int, int, int]
    anomaly_score: float
    final_confidence: float
    confidence_percentage: float
    priority: str
    evidence_scores: EvidenceScoresSummary
    geolocation: GeolocationSummary
    debug_image_path: Optional[str] = None
    image_url: Optional[str] = None
    created_at: datetime


class RouteWaypoint(BaseModel):
    waypoint_index: int
    image_id: Optional[str] = None
    filename: str
    timestamp: Optional[str] = None
    latitude: float
    longitude: float
    detection_latitude: Optional[float] = None
    detection_longitude: Optional[float] = None
    heading: Optional[float] = None
    altitude: Optional[float] = None
    leg_distance_m: Optional[float] = None
    cumulative_distance_m: Optional[float] = None
    total_detections: int = 0
    max_priority: str = "NONE"
    max_confidence: float = 0.0
    matched_by: Optional[str] = None
    matched_json_file: Optional[str] = None
    detection_id: Optional[str] = None
    object_class: Optional[str] = None


class RouteSummary(BaseModel):
    total_waypoints: int
    total_distance_m: float
    total_distance_km: float
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    start_coordinates: Optional[Tuple[float, float]] = None
    end_coordinates: Optional[Tuple[float, float]] = None


class AnalyzeImageResponse(BaseModel):
    image_id: str
    filename: str
    image_dimensions: Tuple[int, int]
    total_detections: int
    detections: List[DetectionResponseItem]
    detector_used: str
    timestamp: str
    survey_latitude: Optional[float] = None
    survey_longitude: Optional[float] = None
    acquisition_timestamp: Optional[str] = None
    matched_by: Optional[str] = None
    matched_json_file: Optional[str] = None
    route_point: Optional[RouteWaypoint] = None
    route: Optional[List[RouteWaypoint]] = None
    route_summary: Optional[RouteSummary] = None
    image_url: Optional[str] = None


class DetectionDetailResponse(BaseModel):
    detection_id: str
    image_id: str
    region_id: str
    bbox: Tuple[int, int, int, int]
    anomaly_score: float
    final_confidence: float
    confidence_percentage: float
    priority: str
    geolocation: GeolocationSummary
    evidence_scores: EvidenceScoresSummary
    debug_image_path: Optional[str] = None
    image_url: Optional[str] = None
    created_at: datetime


class DetectionEvidenceDetailResponse(BaseModel):
    detection_id: str
    shape: EvidenceResult
    texture: EvidenceResult
    shadow: EvidenceResult
    size: EvidenceResult
    context: EvidenceResult
    fusion_audit: Dict[str, Any]


class BatchImageResult(BaseModel):
    image_id: str
    filename: str
    image_dimensions: Tuple[int, int]
    total_detections: int
    max_confidence: float
    max_priority: str
    detections: List[DetectionResponseItem]
    survey_latitude: Optional[float] = None
    survey_longitude: Optional[float] = None
    acquisition_timestamp: Optional[str] = None
    matched_by: Optional[str] = None
    matched_json_file: Optional[str] = None
    route_point: Optional[RouteWaypoint] = None
    image_url: Optional[str] = None
    error: Optional[str] = None


class BatchAnalyzeResponse(BaseModel):
    batch_id: str
    total_images: int
    processed: int
    failed: int
    high_priority_count: int
    medium_priority_count: int
    low_priority_count: int
    results: List[BatchImageResult]
    route: List[RouteWaypoint] = Field(default_factory=list, description="Ordered survey route connecting all georeferenced image coordinates")
    route_summary: Optional[RouteSummary] = None
    timestamp: str
