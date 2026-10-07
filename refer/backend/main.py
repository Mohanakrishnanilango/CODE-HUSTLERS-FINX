"""
FastAPI Microservice for SIH26057 Marine Sonar Intelligence.
Provides endpoints for Faster R-CNN detection and georeferenced telemetry export.
"""
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional

try:
    from .detector import FasterRCNNDetectorService
except ImportError:
    from detector import FasterRCNNDetectorService

app = FastAPI(
    title="SIH26057 Sonar Intelligence API",
    description="Automated Underwater Marine Debris and Anomaly Detection Microservice",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Optional checkpoint path if available
CHECKPOINT = r"E:\SIH26057\SIH_26057_WORK\FasterRCNN_Models\FasterRCNN_Models\fasterrcnn_epoch_01.pth"
detector_service = FasterRCNNDetectorService(checkpoint_path=CHECKPOINT)

class PingPayload(BaseModel):
    ping_id: int
    image: str
    latitude: float
    longitude: float
    heading: float
    altitude: float
    sonar_range: float
    side: str
    target_class: Optional[str] = None
    confidence: Optional[float] = None
    bbox: Optional[List[float]] = None

class DetectionRequest(BaseModel):
    pings: List[PingPayload]

@app.get("/")
def root():
    return {
        "project": "SIH26057 Marine Sonar Intelligence",
        "status": "online",
        "model": "Faster R-CNN ResNet-50 FPN (PyTorch)"
    }

@app.post("/api/detect")
def detect_sonar_anomalies(payload: DetectionRequest):
    detections = []
    for ping in payload.pings:
        # Check if local image exists
        local_img = Path(ping.image.lstrip("/"))
        if not local_img.exists():
            local_img = Path("public") / local_img

        preds = detector_service.predict_image(str(local_img)) if local_img.exists() else []

        if preds:
            top_pred = preds[0]
            detections.append({
                "id": f"det_ping_{ping.ping_id}",
                "ping_id": ping.ping_id,
                "object_class": top_pred["object_class"],
                "display_name": top_pred["object_class"].replace("_", " ").title(),
                "confidence": top_pred["confidence"],
                "latitude": ping.latitude,
                "longitude": ping.longitude,
                "timestamp": "2026-09-23T09:30:00Z",
                "heading_deg": ping.heading,
                "altitude_m": ping.altitude,
                "range_m": ping.sonar_range,
                "side": ping.side,
                "bbox": top_pred["bbox"],
                "image_url": ping.image,
                "is_synthetic": False,
                "position_label": "Detection position from navigation metadata"
            })
        else:
            # Fallback to metadata
            detections.append({
                "id": f"det_ping_{ping.ping_id}",
                "ping_id": ping.ping_id,
                "object_class": ping.target_class or "anomaly",
                "display_name": (ping.target_class or "anomaly").replace("_", " ").title(),
                "confidence": ping.confidence or 0.85,
                "latitude": ping.latitude,
                "longitude": ping.longitude,
                "timestamp": "2026-09-23T09:30:00Z",
                "heading_deg": ping.heading,
                "altitude_m": ping.altitude,
                "range_m": ping.sonar_range,
                "side": ping.side,
                "bbox": ping.bbox or [100, 100, 200, 200],
                "image_url": ping.image,
                "is_synthetic": True,
                "position_label": "Detection position from navigation metadata"
            })

    return {"detections": detections}
