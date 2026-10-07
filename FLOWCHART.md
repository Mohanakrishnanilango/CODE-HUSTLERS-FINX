# GhostNet Detection Pipeline — Decision Flowchart

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        GHOSTNET DETECTION PIPELINE                         │
│                    Smart India Hackathon 2026 — SIH26057                    │
└─────────────────────────────────────────────────────────────────────────────┘

  ┌──────────────┐
  │  SSS Image   │
  │   Upload     │
  └──────┬───────┘
         │
         ▼
  ┌──────────────────────────────────────────────────────────────────────┐
  │                    STEP 1: PREPROCESSING                            │
  │  • Load image (grayscale or RGB)                                    │
  │  • Convert to BGR for YOLO                                          │
  │  • Extract metadata (lat/lon, resolution, heading)                  │
  └──────────────┬───────────────────────────────────────────────────────┘
                 │
                 ▼
  ┌──────────────────────────────────────────────────────────────────────┐
  │                    STEP 2: DUAL YOLO INFERENCE                      │
  │                                                                     │
  │  ┌─────────────────────┐          ┌─────────────────────┐          │
  │  │     MODEL A         │          │     MODEL B         │          │
  │  │   (YOLOv12-nano)    │          │   (YOLOv12)         │          │
  │  │   2.5M params       │          │   11.1M params      │          │
  │  │                     │          │                     │          │
  │  │  1 class:           │          │  5 classes:         │          │
  │  │  • Artificial_Object│          │  • crab_pot         │          │
  │  │                     │          │  • submarine_pipe   │          │
  │  │  Binary detector:   │          │  • shipwreck        │          │
  │  │  "Is it man-made?"  │          │  • ghost_net        │          │
  │  │                     │          │  • mine_cylinder    │          │
  │  └──────────┬──────────┘          └──────────┬──────────┘          │
  │             │                                 │                     │
  │             ▼                                 ▼                     │
  │  ┌──────────────────┐              ┌──────────────────┐            │
  │  │ Raw detections   │              │ Raw detections   │            │
  │  │ (bbox + class    │              │ (bbox + class    │            │
  │  │  + confidence)   │              │  + confidence)   │            │
  │  └────────┬─────────┘              └────────┬─────────┘            │
  │           │                                  │                      │
  │           └──────────┬───────────────────────┘                      │
  │                      ▼                                              │
  │           ┌──────────────────────┐                                  │
  │           │  FILTERING           │                                  │
  │           │  • Min bbox: 3% img  │                                  │
  │           │  • Min conf: 0.50    │                                  │
  │           │  • IoU > 0.3 = merge │                                  │
  │           └──────────┬───────────┘                                  │
  └──────────────────────┼──────────────────────────────────────────────┘
                         │
                         ▼
  ┌──────────────────────────────────────────────────────────────────────┐
  │                    STEP 3: IoU-BASED MERGING                        │
  │                                                                     │
  │  For each detection pair (A_i, B_j):                               │
  │    IoU = |intersection| / |union|                                   │
  │    if IoU > 0.3: merge into same cluster                           │
  │                                                                     │
  │  Output: N clusters, each with A-dets + B-dets                    │
  └──────────────┬───────────────────────────────────────────────────────┘
                 │
                 ▼
  ┌──────────────────────────────────────────────────────────────────────┐
  │                    STEP 4: DUAL-MODEL VOTING                        │
  │                                                                     │
  │  For each cluster:                                                  │
  │                                                                     │
  │  ┌─────────────────────────────────────────────────────────────┐    │
  │  │  VOTE A: Artificial_Object detected?  (YOLO-A)             │    │
  │  │  VOTE B: Which class? (YOLO-B)                             │    │
  │  │           ├─ unnatural: ghost_net, shipwreck, mine,         │    │
  │  │           │  crab_pot, submarine_pipeline                   │    │
  │  │           └─ natural: background, seabed, sand, rock        │    │
  │  └─────────────────────────────────────────────────────────────┘    │
  │                                                                     │
  │  ┌─────────────────────────────────────────────────────────────┐    │
  │  │              DECISION MATRIX                                │    │
  │  │                                                             │    │
  │  │  YOLO-A: artificial  +  YOLO-B: (any)      → STRONG_POS    │    │
  │  │          (anything)  +  YOLO-B: unnatural   → SUPPORT_POS   │    │
  │  │          artificial  +  YOLO-B: natural     → UNCERTAIN     │    │
  │  │          nothing     +  YOLO-B: unnatural   → INVESTIGATE   │    │
  │  │          nothing     +  YOLO-B: nothing     → BACKGROUND    │    │
  │  └─────────────────────────────────────────────────────────────┘    │
  │                                                                     │
  │  Score = 0.5 × score_A + 0.5 × score_B                            │
  │  Apply small-region penalty (< 1% area → ×0.5, < 2% → ×0.75)     │
  └──────────────┬───────────────────────────────────────────────────────┘
                 │
                 ▼
  ┌──────────────────────────────────────────────────────────────────────┐
  │                    STEP 5: EVIDENCE FUSION                          │
  │                                                                     │
  │  For each merged region, compute 5 evidence channels:              │
  │                                                                     │
  │  ┌────────────┐  ┌────────────┐  ┌────────────┐                   │
  │  │   SHAPE    │  │  TEXTURE   │  │   SHADOW   │                   │
  │  │ • Area     │  │ • GLCM     │  │ • Shadow   │                   │
  │  │ • Aspect   │  │ • Contrast │  │   detect   │                   │
  │  │ • Circ.    │  │ • LBP      │  │ • Contrast │                   │
  │  │ • Elong.   │  │ • Energy   │  │   delta    │                   │
  │  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘                   │
  │        │               │               │                           │
  │  ┌────────────┐  ┌────────────┐                                   │
  │  │    SIZE    │  │  CONTEXT   │                                   │
  │  │ • Pixels   │  │ • Bg       │                                   │
  │  │ • Meters   │  │   intensity│                                   │
  │  │ • Extent   │  │ • Wasser-  │                                   │
  │  │            │  │   stein    │                                   │
  │  └─────┬──────┘  └─────┬──────┘                                   │
  │        │               │                                           │
  │        └───────┬───────┘                                           │
  │                ▼                                                   │
  │  ┌──────────────────────────┐                                     │
  │  │  WEIGHTED FUSION         │                                     │
  │  │  anomaly: 0.3            │                                     │
  │  │  shape:    0.2           │                                     │
  │  │  texture:  0.2           │                                     │
  │  │  shadow:   0.2           │                                     │
  │  │  size:     0.1           │                                     │
  │  │  context:  0.0 → redist  │                                     │
  │  │                          │                                     │
  │  │  final_confidence = Σ(wᵢ × scoreᵢ)                            │
  │  └──────────────┬───────────┘                                     │
  └─────────────────┼───────────────────────────────────────────────────┘
                    │
                    ▼
  ┌──────────────────────────────────────────────────────────────────────┐
  │                    STEP 6: PRIORITY CLASSIFICATION                  │
  │                                                                     │
  │  ┌─────────────────────────────────────────────────────────────┐    │
  │  │  final_confidence ≥ 0.70  →  HIGH    (red)                │    │
  │  │  final_confidence ≥ 0.40  →  MEDIUM  (orange)             │    │
  │  │  final_confidence < 0.40  →  LOW     (gray)               │    │
  │  └─────────────────────────────────────────────────────────────┘    │
  │                                                                     │
  │  Output per region:                                                │
  │  • region_id: "dual_01_ghost_net"                                  │
  │  • bbox: [x, y, w, h]                                             │
  │  • confidence_percentage: 88.5%                                    │
  │  • priority: HIGH / MEDIUM / LOW                                   │
  │  • classification: ghost_net / shipwreck / mine_cylinder / etc.   │
  │  • evidence_scores: {shape, texture, shadow, size, context}       │
  │  • geolocation: lat/lon (if metadata available)                   │
  │  • debug_image_path: annotated bounding box image                 │
  └──────────────┬───────────────────────────────────────────────────────┘
                 │
                 ▼
  ┌──────────────────────────────────────────────────────────────────────┐
  │                    STEP 7: API / UI OUTPUT                           │
  │                                                                     │
  │  Single Image:                                                     │
  │    POST /api/detections/analyze                                    │
  │    → { detections: [...], debug_image, map_markers }              │
  │                                                                     │
  │  Batch Processing:                                                 │
  │    POST /api/detections/batch                                      │
  │    → { results: [ {filename, detections[], max_priority}... ],    │
  │         high_priority_count, medium_priority_count }              │
  │                                                                     │
  │  Results sorted: HIGH → MEDIUM → LOW                              │
  └─────────────────────────────────────────────────────────────────────┘
```

## Decision Matrix Summary

| YOLO-A | YOLO-B | Verdict | Score Multiplier |
|--------|--------|---------|-----------------|
| artificial | (any positive) | **STRONG POSITIVE** | 1.0× |
| (anything) | unnatural | **SUPPORTING POSITIVE** | 1.0× |
| artificial | natural | UNCERTAIN | 0.7× |
| nothing | unnatural | INVESTIGATE | 0.8× |
| nothing | natural | INVESTIGATE | 0.5× |
| nothing | nothing | BACKGROUND | — (skip) |

## YOLO-B Class Taxonomy

| Class | Category | Description |
|-------|----------|-------------|
| `ghost_net` | unnatural | Abandoned fishing nets |
| `shipwreck` | unnatural | Sunken vessels/structures |
| `mine_cylinder` | unnatural | Underwater mines/cylinders |
| `crab_pot` | unnatural | Derelict crab pots |
| `submarine_pipeline` | unnatural | Underwater pipes/cables |
