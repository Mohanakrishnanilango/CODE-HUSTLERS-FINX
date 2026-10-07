from datetime import datetime
import os
import uuid
from typing import Any, Dict, List, Optional
import cv2
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import logger
from app.database.session import get_db
from app.dependencies import get_anomaly_detector, resolve_detector
from app.models.detection import Detection
from app.models.evidence import DetectionEvidence
from app.models.survey import SSSImage
from app.schemas.detection import (
    AnalyzeImageResponse,
    BatchAnalyzeResponse,
    BatchImageResult,
    DetectionDetailResponse,
    DetectionEvidenceDetailResponse,
    DetectionResponseItem,
    EvidenceScoresSummary,
    GeolocationSummary,
    RouteSummary,
    RouteWaypoint,
)
from app.schemas.evidence import CompleteEvidenceSet, EvidenceResult
from app.schemas.survey import SurveyMetadata
from app.services.anomaly_detector.base import AnomalyDetector
from app.services.evidence.context import analyze_seafloor_context
from app.services.evidence.fusion import fuse_evidence
from app.services.evidence.shadow import analyze_shadow
from app.services.evidence.shape import analyze_shape
from app.services.evidence.size import analyze_size
from app.services.evidence.texture import analyze_texture
from app.services.geolocation.calculator import calculate_anomaly_geolocation
from app.services.priority.ranker import rank_detections
from app.services.telemetry.parser import (
    TelemetryParser,
    build_survey_route,
    match_image_with_json,
)
from app.services.visualizer.debug_annotator import generate_annotated_debug_image
from app.utils.image_processing import ImageProcessingError, load_and_preprocess_image

router = APIRouter(prefix="/detections", tags=["Detections"])


@router.post("/analyze", response_model=AnalyzeImageResponse, status_code=status.HTTP_201_CREATED)
async def analyze_sss_image(
    file: UploadFile = File(..., description="Side-Scan Sonar (SSS) image file"),
    json_file: Optional[UploadFile] = File(None, description="Optional telemetry JSON file matching the image by filename or timestamp"),
    json_data: Optional[str] = Form(None, description="Optional raw JSON string containing coordinates and telemetry"),
    latitude: Optional[float] = Form(None, description="Survey latitude in WGS84 decimal degrees"),
    longitude: Optional[float] = Form(None, description="Survey longitude in WGS84 decimal degrees"),
    heading: Optional[float] = Form(None, description="Vessel / towfish heading in degrees clockwise from North"),
    resolution: Optional[float] = Form(None, description="Spatial resolution in meters per pixel"),
    nadir_column: Optional[int] = Form(None, description="Image pixel column corresponding to sonar nadir"),
    swath_channel: Optional[str] = Form(None, description="'port', 'starboard', or 'both'"),
    enable_visual_debug: bool = Form(True, description="Generate multi-layer annotated visual debug image"),
    detector_backend: Optional[str] = Form(None, description="Optional override for detector backend ('unet', 'dual_yolo', 'hybrid', 'mock')"),
    db: Session = Depends(get_db),
    detector: AnomalyDetector = Depends(get_anomaly_detector),
) -> AnalyzeImageResponse:
    """
    Primary SSS processing endpoint:
    1. Validates and preprocesses uploaded SSS imagery.
    2. Parses optional telemetry JSON file or data (paired by filename stem or timestamp).
    3. Runs anomaly detection (via pluggable AnomalyDetector interface).
    4. For every candidate region, computes 5 evidence modalities (Shape, Masked GLCM, Sonar Shadow, Size, Context).
    5. Performs explainable fusion with dynamic weight redistribution for missing modalities.
    6. Calculates non-fabricated WGS84 geolocation when survey metadata is sufficient.
    7. Ranks multiple candidate detections by confidence score.
    8. Persists results to database (PostgreSQL + PostGIS).
    9. Optionally saves annotated visual verification image.
    10. Produces survey route waypoint metadata.
    """
    # 1. Read and validate image
    contents = await file.read()
    try:
        image = load_and_preprocess_image(contents)
    except ImageProcessingError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid SSS image upload: {str(e)}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to decode image: {str(e)}",
        )

    img_h, img_w = image.shape[:2]
    image_id = str(uuid.uuid4())
    safe_filename = file.filename or f"sss_{image_id[:8]}.png"

    # Save original image to storage
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    saved_image_path = os.path.join(settings.UPLOAD_DIR, f"{image_id}_{safe_filename}")
    cv2.imwrite(saved_image_path, image)

    # 1.1 Process optional telemetry JSON (file upload or raw form json)
    telem_parser = TelemetryParser()
    if json_file is not None:
        try:
            j_bytes = await json_file.read()
            telem_parser.load_json_content(j_bytes, source_filename=json_file.filename)
        except Exception as j_err:
            logger.warning(f"Failed to read json_file {json_file.filename}: {j_err}")
    if json_data:
        try:
            telem_parser.load_json_content(json_data, source_filename="form_json_data.json")
        except Exception as j_err:
            logger.warning(f"Failed to parse json_data form field: {j_err}")

    match_res = None
    if telem_parser.records:
        match_res = match_image_with_json(safe_filename, telem_parser.records)
        # If not matched by filename/timestamp but records were loaded, associate directly
        if not match_res.matched and telem_parser.records:
            match_res.matched = True
            match_res.matched_by = "single_upload" if len(telem_parser.records) == 1 else "first_record"
            match_res.telemetry = telem_parser.records[0]
            match_res.json_filename = telem_parser.records[0].source_file

    telem = match_res.telemetry if (match_res and match_res.matched) else None

    # Merge coordinates & survey metadata (JSON telemetry takes precedence over manual form inputs)
    effective_lat = telem.latitude if (telem and telem.latitude is not None) else latitude
    effective_lon = telem.longitude if (telem and telem.longitude is not None) else longitude
    effective_heading = telem.heading_deg if (telem and telem.heading_deg is not None) else heading
    effective_res = telem.resolution_m_per_pixel if (telem and telem.resolution_m_per_pixel is not None) else resolution
    effective_nadir = telem.nadir_column if (telem and telem.nadir_column is not None) else nadir_column
    effective_channel = telem.swath_channel if (telem and telem.swath_channel is not None) else swath_channel
    effective_timestamp = (telem.timestamp if (telem and telem.timestamp) else datetime.utcnow().isoformat() + "Z")

    # Build SurveyMetadata
    survey_meta = SurveyMetadata(
        survey_latitude=effective_lat,
        survey_longitude=effective_lon,
        heading_deg=effective_heading,
        resolution_m_per_pixel=effective_res,
        nadir_column=effective_nadir,
        swath_channel=effective_channel,
        acquisition_timestamp=effective_timestamp,
    )

    # Persist SSSImage record
    sss_image_record = SSSImage(
        id=image_id,
        filename=safe_filename,
        file_path=saved_image_path,
        image_width=img_w,
        image_height=img_h,
        survey_lat=effective_lat,
        survey_lon=effective_lon,
        heading_deg=effective_heading,
        resolution_m_per_pixel=effective_res,
        nadir_column=effective_nadir,
        swath_channel=effective_channel,
        acquisition_timestamp=survey_meta.acquisition_timestamp,
    )
    db.add(sss_image_record)

    # 2. Run Anomaly Detection (Pluggable Model)
    active_detector = resolve_detector(detector_backend) if detector_backend else detector
    detection_result = active_detector.predict(image, metadata=survey_meta.model_dump())
    raw_regions = detection_result.regions

    evaluated_candidates: List[Dict[str, Any]] = []

    # 3. Evidence Extraction Pipeline for Each Region
    for r_idx, region in enumerate(raw_regions):
        detection_id = str(uuid.uuid4())
        rx, ry, rw, rh = region.bbox

        # 3.1 Shape Analysis
        shape_ev = analyze_shape(
            mask=region.mask,
            image_shape=(img_h, img_w),
        )

        # 3.2 Acoustic Shadow Analysis (Sonar Geometry)
        shadow_ev, shadow_mask = analyze_shadow(
            image=image,
            anomaly_mask=region.mask,
            bbox=region.bbox,
            metadata=survey_meta,
        )

        # 3.3 Masked GLCM Texture Analysis
        texture_ev = analyze_texture(
            image=image,
            anomaly_mask=region.mask,
            shadow_mask=shadow_mask,
        )

        # 3.4 Descriptive & Metric Size Analysis
        size_ev = analyze_size(
            mask=region.mask,
            bbox=region.bbox,
            metadata=survey_meta,
            require_physical=True,
        )

        # 3.5 Seafloor Context Analysis
        context_ev = analyze_seafloor_context(
            image=image,
            anomaly_mask=region.mask,
            shadow_mask=shadow_mask,
        )

        evidence_set = CompleteEvidenceSet(
            shape=shape_ev,
            texture=texture_ev,
            shadow=shadow_ev,
            size=size_ev,
            context=context_ev,
        )

        # 4. Evidence Fusion with Dynamic Weight Redistribution
        fusion_result = fuse_evidence(
            anomaly_score=region.anomaly_score,
            evidence_set=evidence_set,
        )

        # Filter: Only declare as anomaly if confidence score > 50% (0.50), otherwise skip
        min_threshold = getattr(settings, "MIN_ANOMALY_CONFIDENCE_THRESHOLD", 0.50)
        if fusion_result.final_confidence <= min_threshold:
            logger.info(
                "Region %s confidence %.2f (%.1f%%) <= %.2f threshold; skipping (not an anomaly)",
                region.region_id,
                fusion_result.final_confidence,
                fusion_result.confidence_percentage,
                min_threshold,
            )
            continue

        # 5. Geolocation Calculation (Non-fabricating)
        centroid = (rx + rw / 2.0, ry + rh / 2.0)
        geo_result = calculate_anomaly_geolocation(
            anomaly_centroid=centroid,
            image_shape=(img_h, img_w),
            metadata=survey_meta,
        )

        # 6. Visual Debugger (Annotated HUD overlay)
        debug_img_path = None
        if enable_visual_debug:
            try:
                debug_img_path = generate_annotated_debug_image(
                    original_image=image,
                    anomaly_mask=region.mask,
                    bbox=region.bbox,
                    shadow_mask=shadow_mask,
                    fusion_result=fusion_result,
                    region_id=region.region_id,
                    output_filename=f"{detection_id}_debug.png",
                )
            except Exception as viz_err:
                logger.warning(f"Failed to generate visual debug image for {detection_id}: {viz_err}")

        candidate_data = {
            "detection_id": detection_id,
            "region_id": region.region_id,
            "bbox": (int(rx), int(ry), int(rw), int(rh)),
            "anomaly_score": region.anomaly_score,
            "fusion_result": fusion_result,
            "final_confidence": fusion_result.final_confidence,
            "confidence_percentage": fusion_result.confidence_percentage,
            "priority": fusion_result.priority,
            "evidence_set": evidence_set,
            "geolocation": geo_result,
            "debug_image_path": debug_img_path,
        }
        evaluated_candidates.append(candidate_data)

    # 7. Priority Ranking: Order candidates descending by confidence score
    ranked_candidates = rank_detections(evaluated_candidates)

    # 8. Database Persistence
    response_items: List[DetectionResponseItem] = []
    created_at = datetime.utcnow()

    for cand in ranked_candidates:
        d_id = cand["detection_id"]
        rx, ry, rw, rh = cand["bbox"]
        f_res = cand["fusion_result"]
        g_res = cand["geolocation"]
        ev_set: CompleteEvidenceSet = cand["evidence_set"]

        # Geolocation WKT representation for DB
        geom_val = None
        if g_res.available and g_res.longitude is not None and g_res.latitude is not None:
            geom_val = f"POINT({g_res.longitude} {g_res.latitude})"

        det_record = Detection(
            id=d_id,
            image_id=image_id,
            region_id=cand["region_id"],
            bbox_x=rx,
            bbox_y=ry,
            bbox_w=rw,
            bbox_h=rh,
            anomaly_score=cand["anomaly_score"],
            final_confidence=cand["final_confidence"],
            confidence_percentage=cand["confidence_percentage"],
            priority=cand["priority"],
            latitude=g_res.latitude,
            longitude=g_res.longitude,
            geom=geom_val,
            debug_image_path=cand["debug_image_path"],
            processing_status="COMPLETED",
            created_at=created_at,
        )
        db.add(det_record)

        ev_record = DetectionEvidence(
            id=str(uuid.uuid4()),
            detection_id=d_id,
            shape_features=ev_set.shape.features,
            texture_features=ev_set.texture.features,
            shadow_features=ev_set.shadow.features,
            size_features=ev_set.size.features,
            context_features=ev_set.context.features,
            normalized_scores={
                "shape": ev_set.shape.score,
                "texture": ev_set.texture.score,
                "shadow": ev_set.shadow.score,
                "size": ev_set.size.score,
                "context": ev_set.context.score,
            },
            fusion_audit=f_res.model_dump(),
            created_at=created_at,
        )
        db.add(ev_record)

        response_items.append(
            DetectionResponseItem(
                detection_id=d_id,
                region_id=cand["region_id"],
                rank=cand["rank"],
                bbox=cand["bbox"],
                anomaly_score=cand["anomaly_score"],
                final_confidence=cand["final_confidence"],
                confidence_percentage=cand["confidence_percentage"],
                priority=cand["priority"],
                evidence_scores=EvidenceScoresSummary(
                    shape=ev_set.shape.score,
                    texture=ev_set.texture.score,
                    shadow=ev_set.shadow.score,
                    size=ev_set.size.score,
                    context=ev_set.context.score,
                ),
                geolocation=GeolocationSummary(
                    available=g_res.available,
                    latitude=g_res.latitude,
                    longitude=g_res.longitude,
                    reason=g_res.reason,
                ),
                debug_image_path=cand["debug_image_path"],
                image_url=f"/api/detections/images/{image_id}",
                created_at=created_at,
            )
        )

    db.commit()

    detector_name = active_detector.__class__.__name__

    # Build route point if georeferenced coordinates are available
    route_point = None
    route = None
    route_summary = None
    if effective_lat is not None and effective_lon is not None:
        top_det_id = None
        top_prio = "NONE"
        top_conf = 0.0
        top_det_lat = None
        top_det_lon = None
        if response_items:
            top_det = response_items[0]
            top_det_id = top_det.detection_id
            top_prio = top_det.priority
            top_conf = top_det.final_confidence
            if top_det.geolocation and top_det.geolocation.available and top_det.geolocation.latitude is not None:
                top_det_lat = top_det.geolocation.latitude
                top_det_lon = top_det.geolocation.longitude

        route_point = RouteWaypoint(
            waypoint_index=1,
            image_id=image_id,
            filename=safe_filename,
            timestamp=effective_timestamp,
            latitude=effective_lat,
            longitude=effective_lon,
            detection_latitude=top_det_lat,
            detection_longitude=top_det_lon,
            heading=effective_heading,
            altitude=(telem.altitude_m if telem else None),
            total_detections=len(response_items),
            max_priority=top_prio,
            max_confidence=top_conf,
            matched_by=(match_res.matched_by if match_res and match_res.matched else None),
            matched_json_file=(match_res.json_filename if match_res and match_res.matched else None),
            detection_id=top_det_id,
            object_class=(telem.target_class if telem and telem.target_class else None),
        )

        if len(telem_parser.records) > 1:
            raw_wpts = []
            for idx_rec, rec in enumerate(telem_parser.records):
                if rec.latitude is not None and rec.longitude is not None:
                    raw_wpts.append({
                        "image_id": image_id if idx_rec == 0 else f"ping_{idx_rec+1}",
                        "filename": rec.image_name or (safe_filename if idx_rec == 0 else f"ping_{idx_rec+1}.png"),
                        "timestamp": rec.timestamp or effective_timestamp,
                        "latitude": rec.latitude,
                        "longitude": rec.longitude,
                        "heading": rec.heading_deg,
                        "altitude": rec.altitude_m,
                        "total_detections": len(response_items) if idx_rec == 0 else 0,
                        "max_priority": top_prio if idx_rec == 0 else "NONE",
                        "max_confidence": top_conf if idx_rec == 0 else 0.0,
                        "matched_by": match_res.matched_by if match_res else None,
                        "matched_json_file": rec.source_file,
                    })
            if raw_wpts:
                enr, r_sum = build_survey_route(raw_wpts)
                route = [RouteWaypoint(**w) for w in enr]
                route_summary = RouteSummary(**r_sum)
        else:
            route = [route_point]
            route_summary = RouteSummary(
                total_waypoints=1,
                total_distance_m=0.0,
                total_distance_km=0.0,
                start_time=effective_timestamp,
                end_time=effective_timestamp,
                start_coordinates=(effective_lat, effective_lon),
                end_coordinates=(effective_lat, effective_lon),
            )

    return AnalyzeImageResponse(
        image_id=image_id,
        filename=safe_filename,
        image_dimensions=(img_h, img_w),
        total_detections=len(response_items),
        detections=response_items,
        detector_used=detector_name,
        timestamp=created_at.isoformat() + "Z",
        survey_latitude=effective_lat,
        survey_longitude=effective_lon,
        acquisition_timestamp=effective_timestamp,
        matched_by=(match_res.matched_by if match_res and match_res.matched else None),
        matched_json_file=(match_res.json_filename if match_res and match_res.matched else None),
        route_point=route_point,
        route=route,
        route_summary=route_summary,
        image_url=f"/api/detections/images/{image_id}",
    )


@router.post("/batch", response_model=BatchAnalyzeResponse, status_code=status.HTTP_201_CREATED)
async def batch_analyze_sss_images(
    files: List[UploadFile] = File(..., description="SSS image files and/or telemetry JSON files"),
    json_files: Optional[List[UploadFile]] = File(None, description="Optional separate telemetry JSON files"),
    latitude: Optional[float] = Form(None),
    longitude: Optional[float] = Form(None),
    heading: Optional[float] = Form(None),
    resolution: Optional[float] = Form(None),
    nadir_column: Optional[int] = Form(None),
    swath_channel: Optional[str] = Form(None),
    enable_visual_debug: bool = Form(True),
    detector_backend: Optional[str] = Form(None, description="Optional override for detector backend ('unet', 'dual_yolo', 'hybrid', 'mock')"),
    db: Session = Depends(get_db),
    detector: AnomalyDetector = Depends(get_anomaly_detector),
) -> BatchAnalyzeResponse:
    """
    Batch SSS processing endpoint: accepts multiple image files and telemetry JSON files.
    Pairs images with telemetry by matching filename stem or timestamp, extracts WGS84
    coordinates, runs evidence fusion detection, and constructs the chronological survey route.
    """
    active_detector = resolve_detector(detector_backend) if detector_backend else detector
    batch_id = str(uuid.uuid4())
    created_at = datetime.utcnow()
    results: List[BatchImageResult] = []
    high_count = 0
    medium_count = 0
    low_count = 0
    failed_count = 0

    # Separate image files from JSON files
    image_files: List[UploadFile] = []
    json_uploads: List[UploadFile] = []

    for f in files:
        fname = (f.filename or "").lower()
        if fname.endswith(".json") or (f.content_type and "json" in f.content_type):
            json_uploads.append(f)
        else:
            image_files.append(f)

    if json_files:
        json_uploads.extend(json_files)

    # Parse all telemetry JSON files
    telem_parser = TelemetryParser()
    for jf in json_uploads:
        try:
            j_bytes = await jf.read()
            telem_parser.load_json_content(j_bytes, source_filename=jf.filename)
        except Exception as j_err:
            logger.warning(f"Batch: Failed to read telemetry JSON {jf.filename}: {j_err}")

    raw_route_points: List[Dict[str, Any]] = []

    for i, upload_file in enumerate(image_files):
        try:
            contents = await upload_file.read()
            image = load_and_preprocess_image(contents)
        except Exception as e:
            failed_count += 1
            results.append(BatchImageResult(
                image_id="",
                filename=upload_file.filename or "unknown",
                image_dimensions=(0, 0),
                total_detections=0,
                max_confidence=0.0,
                max_priority="NONE",
                detections=[],
                error=str(e),
            ))
            continue

        img_h, img_w = image.shape[:2]
        image_id = str(uuid.uuid4())
        safe_filename = upload_file.filename or f"sss_{image_id[:8]}.png"

        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
        saved_image_path = os.path.join(settings.UPLOAD_DIR, f"{image_id}_{safe_filename}")
        cv2.imwrite(saved_image_path, image)

        # Match with telemetry records by filename stem, timestamp, or record content
        match_res = match_image_with_json(upload_file.filename or "", telem_parser.records)
        if not match_res.matched and telem_parser.records:
            if len(image_files) == 1:
                match_res.matched = True
                match_res.matched_by = "single_telemetry"
                match_res.telemetry = telem_parser.records[0]
                match_res.json_filename = telem_parser.records[0].source_file
            elif len(telem_parser.records) == len(image_files) and i < len(telem_parser.records):
                match_res.matched = True
                match_res.matched_by = "positional"
                match_res.telemetry = telem_parser.records[i]
                match_res.json_filename = telem_parser.records[i].source_file
            elif len(telem_parser.records) == 1:
                match_res.matched = True
                match_res.matched_by = "single_telemetry"
                match_res.telemetry = telem_parser.records[0]
                match_res.json_filename = telem_parser.records[0].source_file

        telem = match_res.telemetry if (match_res and match_res.matched) else None

        cur_lat = telem.latitude if (telem and telem.latitude is not None) else latitude
        cur_lon = telem.longitude if (telem and telem.longitude is not None) else longitude
        cur_heading = telem.heading_deg if (telem and telem.heading_deg is not None) else heading
        cur_res = telem.resolution_m_per_pixel if (telem and telem.resolution_m_per_pixel is not None) else resolution
        cur_nadir = telem.nadir_column if (telem and telem.nadir_column is not None) else nadir_column
        cur_channel = telem.swath_channel if (telem and telem.swath_channel is not None) else swath_channel
        cur_ts = telem.timestamp if (telem and telem.timestamp) else (created_at.isoformat() + "Z")

        survey_meta = SurveyMetadata(
            survey_latitude=cur_lat,
            survey_longitude=cur_lon,
            heading_deg=cur_heading,
            resolution_m_per_pixel=cur_res,
            nadir_column=cur_nadir,
            swath_channel=cur_channel,
            acquisition_timestamp=cur_ts,
        )

        sss_image_record = SSSImage(
            id=image_id,
            filename=safe_filename,
            file_path=saved_image_path,
            image_width=img_w,
            image_height=img_h,
            survey_lat=cur_lat,
            survey_lon=cur_lon,
            heading_deg=cur_heading,
            resolution_m_per_pixel=cur_res,
            nadir_column=cur_nadir,
            swath_channel=cur_channel,
            acquisition_timestamp=survey_meta.acquisition_timestamp,
        )
        db.add(sss_image_record)

        detection_result = active_detector.predict(image, metadata=survey_meta.model_dump())
        raw_regions = detection_result.regions
        evaluated_candidates: List[Dict[str, Any]] = []

        for region in raw_regions:
            detection_id = str(uuid.uuid4())
            rx, ry, rw, rh = region.bbox

            shape_ev = analyze_shape(mask=region.mask, image_shape=(img_h, img_w))
            shadow_ev, shadow_mask = analyze_shadow(
                image=image, anomaly_mask=region.mask, bbox=region.bbox, metadata=survey_meta,
            )
            texture_ev = analyze_texture(image=image, anomaly_mask=region.mask, shadow_mask=shadow_mask)
            size_ev = analyze_size(mask=region.mask, bbox=region.bbox, metadata=survey_meta, require_physical=True)
            context_ev = analyze_seafloor_context(image=image, anomaly_mask=region.mask, shadow_mask=shadow_mask)

            evidence_set = CompleteEvidenceSet(
                shape=shape_ev, texture=texture_ev, shadow=shadow_ev, size=size_ev, context=context_ev,
            )
            fusion_result = fuse_evidence(anomaly_score=region.anomaly_score, evidence_set=evidence_set)

            # Filter: Only declare as anomaly if confidence score > 50% (0.50), otherwise skip
            min_threshold = getattr(settings, "MIN_ANOMALY_CONFIDENCE_THRESHOLD", 0.50)
            if fusion_result.final_confidence <= min_threshold:
                logger.info(
                    "Batch region %s confidence %.2f (%.1f%%) <= %.2f threshold; skipping (not an anomaly)",
                    region.region_id,
                    fusion_result.final_confidence,
                    fusion_result.confidence_percentage,
                    min_threshold,
                )
                continue

            centroid = (rx + rw / 2.0, ry + rh / 2.0)
            geo_result = calculate_anomaly_geolocation(
                anomaly_centroid=centroid, image_shape=(img_h, img_w), metadata=survey_meta,
            )

            debug_img_path = None
            if enable_visual_debug:
                try:
                    debug_img_path = generate_annotated_debug_image(
                        original_image=image, anomaly_mask=region.mask, bbox=region.bbox,
                        shadow_mask=shadow_mask, fusion_result=fusion_result,
                        region_id=region.region_id, output_filename=f"{detection_id}_debug.png",
                    )
                except Exception:
                    pass

            evaluated_candidates.append({
                "detection_id": detection_id, "region_id": region.region_id,
                "bbox": (int(rx), int(ry), int(rw), int(rh)),
                "anomaly_score": region.anomaly_score, "fusion_result": fusion_result,
                "final_confidence": fusion_result.final_confidence,
                "confidence_percentage": fusion_result.confidence_percentage,
                "priority": fusion_result.priority, "evidence_set": evidence_set,
                "geolocation": geo_result, "debug_image_path": debug_img_path,
            })

        ranked = rank_detections(evaluated_candidates)
        det_items: List[DetectionResponseItem] = []
        img_max_conf = 0.0
        img_max_priority = "NONE"

        for cand in ranked:
            d_id = cand["detection_id"]
            f_res = cand["fusion_result"]
            g_res = cand["geolocation"]
            ev_set: CompleteEvidenceSet = cand["evidence_set"]

            geom_val = None
            if g_res.available and g_res.longitude is not None and g_res.latitude is not None:
                geom_val = f"POINT({g_res.longitude} {g_res.latitude})"

            db.add(Detection(
                id=d_id, image_id=image_id, region_id=cand["region_id"],
                bbox_x=cand["bbox"][0], bbox_y=cand["bbox"][1],
                bbox_w=cand["bbox"][2], bbox_h=cand["bbox"][3],
                anomaly_score=cand["anomaly_score"],
                final_confidence=cand["final_confidence"],
                confidence_percentage=cand["confidence_percentage"],
                priority=cand["priority"],
                latitude=g_res.latitude, longitude=g_res.longitude, geom=geom_val,
                debug_image_path=cand["debug_image_path"],
                processing_status="COMPLETED", created_at=created_at,
            ))

            db.add(DetectionEvidence(
                id=str(uuid.uuid4()), detection_id=d_id,
                shape_features=ev_set.shape.features, texture_features=ev_set.texture.features,
                shadow_features=ev_set.shadow.features, size_features=ev_set.size.features,
                context_features=ev_set.context.features,
                normalized_scores={
                    "shape": ev_set.shape.score, "texture": ev_set.texture.score,
                    "shadow": ev_set.shadow.score, "size": ev_set.size.score,
                    "context": ev_set.context.score,
                },
                fusion_audit=f_res.model_dump(), created_at=created_at,
            ))

            if cand["final_confidence"] > img_max_conf:
                img_max_conf = cand["final_confidence"]
                img_max_priority = cand["priority"]

            det_items.append(DetectionResponseItem(
                detection_id=d_id, region_id=cand["region_id"], rank=cand.get("rank", 0),
                bbox=cand["bbox"], anomaly_score=cand["anomaly_score"],
                final_confidence=cand["final_confidence"],
                confidence_percentage=cand["confidence_percentage"],
                priority=cand["priority"],
                evidence_scores=EvidenceScoresSummary(
                    shape=ev_set.shape.score, texture=ev_set.texture.score,
                    shadow=ev_set.shadow.score, size=ev_set.size.score,
                    context=ev_set.context.score,
                ),
                geolocation=GeolocationSummary(
                    available=g_res.available, latitude=g_res.latitude,
                    longitude=g_res.longitude, reason=g_res.reason,
                ),
                debug_image_path=cand["debug_image_path"],
                image_url=f"/api/detections/images/{image_id}",
                created_at=created_at,
            ))

        if not det_items:
            img_max_priority = "NONE"
        elif img_max_priority == "HIGH":
            high_count += 1
        elif img_max_priority == "MEDIUM":
            medium_count += 1
        elif img_max_priority == "LOW":
            low_count += 1

        # Register waypoint for route if georeferenced coordinates are known
        if cur_lat is not None and cur_lon is not None:
            top_det_id = None
            top_det_lat = None
            top_det_lon = None
            if det_items:
                top_geo = det_items[0].geolocation
                if top_geo and top_geo.available and top_geo.latitude is not None:
                    top_det_lat = top_geo.latitude
                    top_det_lon = top_geo.longitude
                top_det_id = det_items[0].detection_id

            raw_route_points.append({
                "image_id": image_id,
                "filename": safe_filename,
                "timestamp": cur_ts,
                "latitude": cur_lat,
                "longitude": cur_lon,
                "detection_latitude": top_det_lat,
                "detection_longitude": top_det_lon,
                "heading": cur_heading,
                "altitude": (telem.altitude_m if telem else None),
                "total_detections": len(det_items),
                "max_priority": img_max_priority,
                "max_confidence": img_max_conf,
                "matched_by": (match_res.matched_by if match_res and match_res.matched else None),
                "matched_json_file": (match_res.json_filename if match_res and match_res.matched else None),
                "detection_id": top_det_id,
                "object_class": (telem.target_class if telem and telem.target_class else None),
            })

        results.append(BatchImageResult(
            image_id=image_id, filename=safe_filename,
            image_dimensions=(img_h, img_w),
            total_detections=len(det_items),
            max_confidence=img_max_conf, max_priority=img_max_priority,
            detections=det_items,
            survey_latitude=cur_lat,
            survey_longitude=cur_lon,
            acquisition_timestamp=cur_ts,
            matched_by=(match_res.matched_by if match_res and match_res.matched else None),
            matched_json_file=(match_res.json_filename if match_res and match_res.matched else None),
            image_url=f"/api/detections/images/{image_id}",
        ))

    # If a single image was uploaded but JSON telemetry contains multiple mission records, populate full route
    if len(image_files) == 1 and len(telem_parser.records) > 1:
        for idx_rec in range(1, len(telem_parser.records)):
            rec = telem_parser.records[idx_rec]
            if rec.latitude is not None and rec.longitude is not None:
                raw_route_points.append({
                    "image_id": f"ping_{idx_rec + 1}",
                    "filename": rec.image_name or f"ping_{idx_rec + 1}.png",
                    "timestamp": rec.timestamp or (created_at.isoformat() + "Z"),
                    "latitude": rec.latitude,
                    "longitude": rec.longitude,
                    "heading": rec.heading_deg,
                    "altitude": rec.altitude_m,
                    "total_detections": 0,
                    "max_priority": "NONE",
                    "max_confidence": 0.0,
                    "matched_by": "survey_route_log",
                    "matched_json_file": rec.source_file,
                })

    # Construct ordered survey route
    enriched_wpts, route_summary_dict = build_survey_route(raw_route_points)
    route_waypoints = [RouteWaypoint(**w) for w in enriched_wpts]
    route_summary = RouteSummary(**route_summary_dict) if enriched_wpts else None

    # Attach route points back to corresponding BatchImageResults
    wpt_map = {w.image_id: w for w in route_waypoints if w.image_id}
    for res in results:
        if res.image_id in wpt_map:
            res.route_point = wpt_map[res.image_id]

    results.sort(key=lambda r: (
        {"HIGH": 0, "MEDIUM": 1, "LOW": 2, "NONE": 3}.get(r.max_priority, 3),
        -r.max_confidence,
    ))

    db.commit()

    return BatchAnalyzeResponse(
        batch_id=batch_id, total_images=len(image_files),
        processed=len(image_files) - failed_count, failed=failed_count,
        high_priority_count=high_count, medium_priority_count=medium_count,
        low_priority_count=low_count, results=results,
        route=route_waypoints,
        route_summary=route_summary,
        timestamp=created_at.isoformat() + "Z",
    )


@router.get("", response_model=List[DetectionResponseItem])
def list_detections(
    priority: Optional[str] = Query(None, description="Filter by priority: LOW, MEDIUM, or HIGH"),
    min_confidence: Optional[float] = Query(None, ge=0.0, le=1.0, description="Minimum confidence score"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> List[DetectionResponseItem]:
    """Retrieves paginated detections with optional priority and confidence filtering."""
    query = db.query(Detection)
    if priority:
        query = query.filter(Detection.priority == priority.upper())
    if min_confidence is not None:
        query = query.filter(Detection.final_confidence >= min_confidence)

    detections = query.order_by(Detection.final_confidence.desc()).offset(skip).limit(limit).all()

    items = []
    for rank_idx, d in enumerate(detections, start=skip + 1):
        scores = {}
        if d.evidence and d.evidence.normalized_scores:
            scores = d.evidence.normalized_scores

        items.append(
            DetectionResponseItem(
                detection_id=d.id,
                region_id=d.region_id,
                rank=rank_idx,
                bbox=(d.bbox_x, d.bbox_y, d.bbox_w, d.bbox_h),
                anomaly_score=d.anomaly_score,
                final_confidence=d.final_confidence,
                confidence_percentage=d.confidence_percentage,
                priority=d.priority,
                evidence_scores=EvidenceScoresSummary(
                    shape=scores.get("shape"),
                    texture=scores.get("texture"),
                    shadow=scores.get("shadow"),
                    size=scores.get("size"),
                    context=scores.get("context"),
                ),
                geolocation=GeolocationSummary(
                    available=d.latitude is not None and d.longitude is not None,
                    latitude=d.latitude,
                    longitude=d.longitude,
                    reason=None if (d.latitude is not None) else "Missing survey geolocation metadata",
                ),
                debug_image_path=d.debug_image_path,
                created_at=d.created_at,
            )
        )
    return items


@router.get("/high-priority", response_model=List[DetectionResponseItem])
def get_high_priority_detections(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> List[DetectionResponseItem]:
    """Convenience endpoint returning only HIGH priority detections."""
    return list_detections(priority="HIGH", skip=skip, limit=limit, db=db)


@router.get("/images/{image_id}")
def get_sss_image(image_id: str, db: Session = Depends(get_db)) -> FileResponse:
    """Streams the original uploaded SSS image by image ID."""
    img = db.query(SSSImage).filter(SSSImage.id == image_id).first()
    if img and img.file_path and os.path.exists(img.file_path):
        ext = os.path.splitext(img.file_path)[1].lower()
        media_type = "image/png" if ext == ".png" else ("image/jpeg" if ext in [".jpg", ".jpeg"] else "application/octet-stream")
        return FileResponse(img.file_path, media_type=media_type)

    # Fallback search in UPLOAD_DIR by ID prefix or filename match
    if os.path.exists(settings.UPLOAD_DIR):
        for fname in os.listdir(settings.UPLOAD_DIR):
            if fname.startswith(image_id) or fname == image_id:
                cand_path = os.path.join(settings.UPLOAD_DIR, fname)
                ext = os.path.splitext(fname)[1].lower()
                media_type = "image/png" if ext == ".png" else ("image/jpeg" if ext in [".jpg", ".jpeg"] else "application/octet-stream")
                return FileResponse(cand_path, media_type=media_type)

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Uploaded image not found")


@router.get("/{detection_id}", response_model=DetectionDetailResponse)
def get_detection(detection_id: str, db: Session = Depends(get_db)) -> DetectionDetailResponse:
    """Retrieves single detection details by ID."""
    d = db.query(Detection).filter(Detection.id == detection_id).first()
    if not d:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Detection not found")

    scores = {}
    if d.evidence and d.evidence.normalized_scores:
        scores = d.evidence.normalized_scores

    return DetectionDetailResponse(
        detection_id=d.id,
        image_id=d.image_id,
        region_id=d.region_id,
        bbox=(d.bbox_x, d.bbox_y, d.bbox_w, d.bbox_h),
        anomaly_score=d.anomaly_score,
        final_confidence=d.final_confidence,
        confidence_percentage=d.confidence_percentage,
        priority=d.priority,
        geolocation=GeolocationSummary(
            available=d.latitude is not None and d.longitude is not None,
            latitude=d.latitude,
            longitude=d.longitude,
            reason=None if (d.latitude is not None) else "Missing survey geolocation metadata",
        ),
        evidence_scores=EvidenceScoresSummary(
            shape=scores.get("shape"),
            texture=scores.get("texture"),
            shadow=scores.get("shadow"),
            size=scores.get("size"),
            context=scores.get("context"),
        ),
        debug_image_path=d.debug_image_path,
        image_url=f"/api/detections/images/{d.image_id}",
        created_at=d.created_at,
    )


@router.get("/{detection_id}/evidence", response_model=DetectionEvidenceDetailResponse)
def get_detection_evidence(detection_id: str, db: Session = Depends(get_db)) -> DetectionEvidenceDetailResponse:
    """Retrieves complete multi-modal evidence breakdown, raw measurements, and fusion audit."""
    ev = db.query(DetectionEvidence).filter(DetectionEvidence.detection_id == detection_id).first()
    if not ev:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidence record not found")

    scores = ev.normalized_scores or {}

    def make_result(modality_name: str, features: Dict[str, Any]) -> EvidenceResult:
        sc = scores.get(modality_name)
        avail = sc is not None
        reason = None if avail else "Modality unavailable or skipped"
        return EvidenceResult(available=avail, score=sc, features=features or {}, reason=reason)

    return DetectionEvidenceDetailResponse(
        detection_id=detection_id,
        shape=make_result("shape", ev.shape_features),
        texture=make_result("texture", ev.texture_features),
        shadow=make_result("shadow", ev.shadow_features),
        size=make_result("size", ev.size_features),
        context=make_result("context", ev.context_features),
        fusion_audit=ev.fusion_audit or {},
    )


@router.get("/{detection_id}/debug-image")
def get_detection_debug_image(detection_id: str, db: Session = Depends(get_db)) -> FileResponse:
    """Streams the visual debug annotated image artifact for this detection."""
    d = db.query(Detection).filter(Detection.id == detection_id).first()
    if not d:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Detection not found")

    if not d.debug_image_path or not os.path.exists(d.debug_image_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Debug image not available")

    return FileResponse(d.debug_image_path, media_type="image/png")


@router.get("/{detection_id}/original-image")
def get_detection_original_image(detection_id: str, db: Session = Depends(get_db)) -> FileResponse:
    """Streams the original uploaded SSS image for a given detection."""
    d = db.query(Detection).filter(Detection.id == detection_id).first()
    if not d:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Detection not found")
    return get_sss_image(image_id=d.image_id, db=db)
