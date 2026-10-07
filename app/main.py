from contextlib import asynccontextmanager
import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.detection import router as detection_router
from app.api.routes.reports import router as reports_router
from app.core.config import settings
from app.core.logging import logger
from app.database.session import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Ensure storage folders exist and database schema is ready
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    os.makedirs(settings.DEBUG_OUTPUT_DIR, exist_ok=True)
    os.makedirs(settings.REPORT_OUTPUT_DIR, exist_ok=True)
    init_db()
    logger.info("Ghost Net Detection Backend started successfully.")
    yield
    logger.info("Ghost Net Detection Backend shutting down.")


app = FastAPI(
    title=settings.PROJECT_NAME,
    description=(
        "Backend system for Ghost Net Detection using Side-Scan Sonar (SSS) Imagery. "
        "Extracts multi-modal acoustic evidence (shape, masked GLCM texture, acoustic shadow, "
        "metric size, seafloor context), fuses evidence into an explainable confidence score, "
        "ranks priority, performs non-fabricating WGS84 geolocation, persists to PostgreSQL/PostGIS, "
        "and produces diagnostic visual debugging HUDs."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# Enable CORS for Frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

# Register API Routers
app.include_router(detection_router, prefix=settings.API_V1_PREFIX)
app.include_router(reports_router, prefix=settings.API_V1_PREFIX)

# Mount static assets (images, fixtures, HUD resources)
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")



@app.get("/", tags=["Landing"])
def root(request: Request):
    """
    Serves the landing page with navigation to all views for browsers,
    or service status JSON for API clients.
    """
    accept = request.headers.get("accept", "")
    landing_path = os.path.join(os.path.dirname(__file__), "static", "index.html")
    if "text/html" in accept and os.path.exists(landing_path):
        return FileResponse(landing_path, media_type="text/html")

    return {
        "status": "online",
        "service": settings.PROJECT_NAME,
        "detector_backend": settings.DETECTOR_BACKEND,
        "api_docs": "/docs",
        "dashboard": "/dashboard",
        "batch": "/batch",
        "version": "1.0.0",
    }


@app.get("/landing", response_class=FileResponse, tags=["Landing"])
def get_landing():
    """Serves the interactive Ghost Net SSS Sentinel landing page."""
    landing_path = os.path.join(os.path.dirname(__file__), "static", "index.html")
    return FileResponse(landing_path)



@app.get("/dashboard", response_class=FileResponse, tags=["Dashboard"])
def get_dashboard():
    """Serves the interactive Ghost Net SSS Sentinel single-image dashboard."""
    dashboard_path = os.path.join(os.path.dirname(__file__), "static", "dashboard.html")
    return FileResponse(dashboard_path)
 
 
@app.get("/map", response_class=FileResponse, tags=["Dashboard"])
def get_map_view():
    """Serves the georeferenced detection map directly."""
    dashboard_path = os.path.join(os.path.dirname(__file__), "static", "dashboard.html")
    return FileResponse(dashboard_path)


@app.get("/batch", response_class=FileResponse, tags=["Dashboard"])
def get_batch_dashboard():
    """Serves the batch analysis dashboard for processing multiple SSS images."""
    dashboard_path = os.path.join(os.path.dirname(__file__), "static", "batch.html")
    return FileResponse(dashboard_path)


@app.get("/health")
def health_check():
    return {"status": "healthy"}


@app.get("/api/status")
def api_status():
    return {
        "status": "online",
        "detector_backend": settings.DETECTOR_BACKEND,
        "version": "1.0.0",
    }
