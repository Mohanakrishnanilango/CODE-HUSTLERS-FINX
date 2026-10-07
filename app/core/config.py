from typing import Dict, List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # API Settings
    PROJECT_NAME: str = "Ghost Net Detection Backend (SSS)"
    API_V1_PREFIX: str = "/api"
    DEBUG: bool = False

    # Detector Backend: 'unet', 'dual_yolo', 'hybrid', 'teammate', or 'mock'
    DETECTOR_BACKEND: str = "unet"
    TEAMMATE_MODEL_PATH: Optional[str] = None
    TEAMMATE_DEVICE: str = "cpu"  # or 'cuda'

    # UNet Model Configuration (ResNet34 UNet)
    UNET_MODEL_PATH: str = "ml/best_unet.pth"
    UNET_CONFIDENCE_THRESHOLD: float = 0.50
    UNET_MIN_AREA_PX: int = 100

    # Dual YOLO Model Paths
    DUAL_YOLO_MODEL_A: str = "weights/model_a.pt"
    DUAL_YOLO_MODEL_B: str = "weights/model_b.pt"
    DUAL_YOLO_CONFIDENCE: float = 0.25

    # Evidence Fusion Initial Weights (Engineering priors, configurable & tuneable)
    WEIGHT_ANOMALY: float = 0.30
    WEIGHT_SHAPE: float = 0.20
    WEIGHT_TEXTURE: float = 0.20
    WEIGHT_SHADOW: float = 0.15
    WEIGHT_SIZE: float = 0.05
    WEIGHT_CONTEXT: float = 0.10

    # Priority & Anomaly Classification Thresholds
    # Detections with confidence <= 0.50 (50%) are skipped (not classified as anomaly)
    MIN_ANOMALY_CONFIDENCE_THRESHOLD: float = 0.50
    PRIORITY_HIGH_THRESHOLD: float = 0.70
    PRIORITY_MEDIUM_THRESHOLD: float = 0.50

    # Sonar Shadow Analysis Configuration
    # Options: 'metadata_based', 'away_from_nadir', 'port', 'starboard', 'adaptive'
    SHADOW_DIRECTION_MODE: str = "metadata_based"
    SHADOW_PERCENTILE_CUTOFF: float = 15.0
    SHADOW_SIGMA_FACTOR: float = 1.5
    SHADOW_ABSOLUTE_MAX_INTENSITY: int = 35
    SHADOW_ADJACENCY_MAX_DISTANCE_PX: int = 8
    SHADOW_MIN_AREA_PX: int = 8

    # GLCM Texture Configuration
    GLCM_NUM_LEVELS: int = 16
    GLCM_DISTANCES: List[int] = [1, 3]
    GLCM_MIN_VALID_PIXELS: int = 16

    # Context Analysis Configuration
    CONTEXT_DILATION_RADIUS_PX: int = 25
    CONTEXT_MIN_BACKGROUND_PIXELS: int = 32

    # Shape Analysis Configuration
    SHAPE_MIN_CONTOUR_AREA_PX: int = 10

    # Storage Paths
    UPLOAD_DIR: str = "storage/uploads"
    DEBUG_OUTPUT_DIR: str = "storage/debug_outputs"
    REPORT_OUTPUT_DIR: str = "storage/reports"

    # Database Configuration
    # Defaults to PostgreSQL with PostGIS, supports SQLite for local offline testing
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/ghostnet_db"
    SQLITE_TEST_DB: str = "sqlite:///./test_ghostnet.db"
    USE_SQLITE_TEST: bool = False


settings = Settings()
