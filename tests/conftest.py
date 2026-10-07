import io
import os
import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

# Ensure test mode uses SQLite and Mock detector for repeatable isolated tests
os.environ["USE_SQLITE_TEST"] = "True"
os.environ["DETECTOR_BACKEND"] = "mock"
from app.core.config import settings
settings.USE_SQLITE_TEST = True
settings.DETECTOR_BACKEND = "mock"
settings.DATABASE_URL = "sqlite:///./test_ghostnet.db"
settings.SQLITE_TEST_DB = "sqlite:///./test_ghostnet.db"
settings.DEBUG_OUTPUT_DIR = "storage/test_debug_outputs"
settings.UPLOAD_DIR = "storage/test_uploads"

from app.dependencies import get_anomaly_detector
get_anomaly_detector.cache_clear()

from app.database.base import Base
from app.database.session import engine, init_db
from app.main import app



@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    """Initializes SQLite database tables for tests."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    # Cleanup SQLite db file after test session
    Base.metadata.drop_all(bind=engine)
    if os.path.exists("./test_ghostnet.db"):
        try:
            os.remove("./test_ghostnet.db")
        except Exception:
            pass


@pytest.fixture
def client():
    """FastAPI TestClient fixture."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def sample_sss_image_bytes() -> bytes:
    """Creates a synthetic 200x200 SSS image encoded as PNG bytes with an acoustic anomaly."""
    # Background seabed: mean 80 with slight Gaussian acoustic speckle
    rng = np.random.RandomState(42)
    seabed = rng.normal(80, 10, size=(200, 200)).clip(0, 255).astype(np.uint8)

    # Add bright anomaly highlight and acoustic shadow
    # Target region center: ~ (116, 90) and (95, 95)
    seabed[75:115, 80:125] = 225
    # Acoustic shadow adjacent to highlight (covers both port and starboard nadir directions)
    seabed[75:115, 45:75] = 12
    seabed[75:115, 125:155] = 12

    # Encode as PNG bytes
    success, buffer = cv2.imencode(".png", seabed)
    assert success
    return buffer.tobytes()
