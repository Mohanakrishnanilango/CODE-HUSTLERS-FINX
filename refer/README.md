# SIH26057 - AI-Powered Automated Underwater Marine Debris & Anomaly Detection System
### Side-Scan Sonar Imagery Intelligence Dashboard MVP

This package contains the complete, self-contained **Marine Sonar Analysis Dashboard** built for problem statement **SIH26057**.

---

## What Is Included

```
MAP/
├── src/
│   ├── components/       # SonarMap (Leaflet), SonarViewer, SonarUploader, DetectionTable, etc.
│   ├── services/         # Modular SonarParser, DetectionService, GeolocationService, ReportService
│   ├── types/            # TypeScript schemas for Pings, Telemetry, and Detections
│   ├── data/             # Bundled synthetic fixtures and metadata
│   ├── pages/            # Dashboard page layout
│   ├── App.tsx
│   ├── main.tsx
│   └── index.css         # Dark marine sonar theme and Leaflet CSS
├── public/
│   ├── images/           # Authentic side-scan sonar waterfall ping PNGs (ping_0001 to ping_0005)
│   └── fixtures/         # Synthetic .xtf and .jsf text fixture files with Arabian Sea coordinates
├── backend/              # Lightweight Python FastAPI service ready for Faster R-CNN PyTorch weights
│   ├── main.py
│   └── detector.py
├── dist/                 # Pre-built production distribution
├── package.json
├── vite.config.ts
├── tsconfig.json
├── tsconfig.node.json
├── tailwind.config.js
├── postcss.config.js
├── index.html
└── README.md
```

---

## Quick Start Guide

### Step 1: Install Dependencies
Open terminal in this directory and run:
```bash
npm install
```

### Step 2: Start the Dashboard
```bash
npm run dev
```
Open your browser at **http://localhost:5173**.

---

## Key Features

1. **Dual-Mode Sonar Parser (`ISonarParser`)**:
   - Inspects file headers to distinguish between vendor binary logs and synthetic testbed fixtures.
   - Parses `.XTF` and `.JSF` text fixtures into ping records, imagery paths, and navigation metadata.

2. **Interactive Leaflet Georeferenced Map**:
   - OpenStreetMap dark tiles with direct coordinate projection `[latitude, longitude]`.
   - Distinct marker colors per object class (`ghost_net`, `pipeline`, `shipwreck`, `fishing_gear`, `mine_cylinder`).
   - Popups showing object name, confidence, coordinates, heading, altitude, sonar range, and channel side.
   - Two-way click synchronization between map markers, sonar waterfall viewer, and detection table.

3. **Acoustic Waterfall Imagery Viewer**:
   - Renders actual side-scan sonar ping imagery with responsive bounding boxes and reticles.
   - Interactive ping record navigation (`Ping 0001` through `Ping 0005`).

4. **Modular AI Detector Interface (`IDetector`)**:
   - Active: `SyntheticDetector` (clearly labeled "Synthetic Detection").
   - Pluggable: `FasterRCNNDetector` interface ready for ResNet-50 FPN PyTorch model inference.

5. **Dynamic Survey Analytics & Export**:
   - Dynamic record & detection counts and average confidence calculation.
   - 1-click **Download JSON** and **Download CSV** reports with full spatial telemetry.
