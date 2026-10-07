#!/usr/bin/env python3
"""
GhostNet SSS Sentinel - Environment & Setup Diagnostic Tool
Checks Python version, dependencies, model weights, database connectivity,
storage paths, and pipeline sanity.
"""

import sys
import os
from pathlib import Path

# Ensure project root is in path
ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR))
os.chdir(ROOT_DIR)

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def check_python_version() -> bool:
    print(f"{BOLD}[1/6] Checking Python version...{RESET}")
    v = sys.version_info
    print(f"      Current version: {v.major}.{v.minor}.{v.micro}")
    if v < (3, 10):
        print(f"      {RED}[FAIL] Python 3.10+ required.{RESET}")
        return False
    print(f"      {GREEN}[OK] Python version is compatible.{RESET}")
    return True


def check_packages() -> bool:
    print(f"\n{BOLD}[2/6] Checking required packages...{RESET}")
    modules = [
        ("fastapi", "FastAPI web framework"),
        ("uvicorn", "ASGI web server"),
        ("pydantic", "Data schemas and validation"),
        ("pydantic_settings", "Settings management"),
        ("cv2", "OpenCV image processing"),
        ("numpy", "Numerical computing"),
        ("scipy", "Scientific computing"),
        ("skimage", "scikit-image GLCM / texture"),
        ("PIL", "Pillow image library"),
        ("torch", "PyTorch deep learning"),
        ("torchvision", "PyTorch vision utilities"),
        ("ultralytics", "YOLO neural network engine"),
        ("sqlalchemy", "SQLAlchemy ORM"),
        ("httpx", "HTTP client for tests & API"),
        ("pytest", "Pytest testing framework"),
    ]

    all_passed = True
    for mod_name, desc in modules:
        try:
            __import__(mod_name)
            print(f"      {GREEN}[OK]{RESET} {mod_name:<18} ({desc})")
        except ImportError as e:
            print(f"      {RED}[FAIL]{RESET} {mod_name:<18} ({desc}) - Missing: {e}")
            all_passed = False
    return all_passed


def check_directories() -> bool:
    print(f"\n{BOLD}[3/6] Checking storage directories...{RESET}")
    from app.core.config import settings

    dirs = [
        settings.UPLOAD_DIR,
        settings.DEBUG_OUTPUT_DIR,
        settings.REPORT_OUTPUT_DIR,
    ]

    all_ok = True
    for d in dirs:
        p = Path(d)
        try:
            p.mkdir(parents=True, exist_ok=True)
            test_file = p / ".test_write"
            test_file.touch()
            test_file.unlink()
            print(f"      {GREEN}[OK]{RESET} Directory writable: {d}")
        except Exception as e:
            print(f"      {RED}[FAIL]{RESET} Directory error {d}: {e}")
            all_ok = False
    return all_ok


def check_weights() -> bool:
    print(f"\n{BOLD}[4/6] Checking YOLO model weights...{RESET}")
    from app.core.config import settings

    weights = [
        ("Model A (Binary Detector)", settings.DUAL_YOLO_MODEL_A),
        ("Model B (Multi-class Detector)", settings.DUAL_YOLO_MODEL_B),
    ]

    all_ok = True
    for name, path_str in weights:
        p = Path(path_str)
        if p.exists() and p.is_file():
            size_mb = p.stat().st_size / (1024 * 1024)
            print(f"      {GREEN}[OK]{RESET} {name}: {path_str} ({size_mb:.2f} MB)")
        else:
            print(f"      {YELLOW}[WARN]{RESET} {name} not found at: {path_str}")
            all_ok = False

    return all_ok


def check_database() -> bool:
    print(f"\n{BOLD}[5/6] Checking database schema & connectivity...{RESET}")
    from app.core.config import settings
    from app.database.session import engine, init_db
    from sqlalchemy import inspect

    try:
        init_db()
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        expected = ["sss_images", "detections", "detection_evidences"]
        missing = [t for t in expected if t not in tables]

        if not missing:
            print(f"      {GREEN}[OK]{RESET} Database connected. Tables present: {', '.join(tables)}")
            return True
        else:
            print(f"      {YELLOW}[WARN]{RESET} Connected, but missing tables: {missing}")
            return False
    except Exception as e:
        print(f"      {RED}[FAIL]{RESET} Database error: {e}")
        return False


def check_detector_inference() -> bool:
    print(f"\n{BOLD}[6/6] Verifying detection pipeline...{RESET}")
    from app.core.config import settings

    try:
        backend = settings.DETECTOR_BACKEND.lower()
        print(f"      Active detector backend in .env: {CYAN}{backend}{RESET}")

        if backend == "dual_yolo":
            from app.services.anomaly_detector.dual_yolo_detector import DualYOLODetector
            import cv2
            detector = DualYOLODetector()
            sample_path = "test_images/test_sonar_01.png"
            if os.path.exists(sample_path):
                img = cv2.imread(sample_path)
                result = detector.predict(img)
                print(f"      {GREEN}[OK]{RESET} DualYOLODetector inference test passed! Detected {len(result.regions)} region(s) in {sample_path}.")
            else:
                print(f"      {GREEN}[OK]{RESET} DualYOLODetector initialized successfully.")
        else:
            from app.services.anomaly_detector.mock_detector import MockAnomalyDetector
            detector = MockAnomalyDetector()
            import numpy as np
            dummy = np.zeros((100, 100, 3), dtype=np.uint8)
            res = detector.predict(dummy)
            print(f"      {GREEN}[OK]{RESET} MockAnomalyDetector ready. Produced {len(res.regions)} test region(s).")
        return True
    except Exception as e:
        print(f"      {RED}[FAIL]{RESET} Pipeline verification failed: {e}")
        return False


def main():
    print(f"\n{CYAN}{BOLD}======================================================{RESET}")
    print(f"{CYAN}{BOLD}  GHOSTNET SSS SENTINEL - SETUP VERIFICATION{RESET}")
    print(f"{CYAN}{BOLD}======================================================{RESET}\n")

    p1 = check_python_version()
    p2 = check_packages()
    p3 = check_directories()
    p4 = check_weights()
    p5 = check_database()
    p6 = check_detector_inference()

    print(f"\n{CYAN}{BOLD}======================================================{RESET}")
    if p1 and p2 and p3 and p4 and p5 and p6:
        print(f"{GREEN}{BOLD}  ALL CHECKS PASSED! Project setup is 100% complete.{RESET}")
        print(f"  Start the server with:  {BOLD}start.bat{RESET} or {BOLD}python start_server.py{RESET}")
    else:
        print(f"{YELLOW}{BOLD}  SOME CHECKS RETURNED WARNINGS OR FAILURES.{RESET}")
        print(f"  Please review the details above.")
    print(f"{CYAN}{BOLD}======================================================{RESET}\n")


if __name__ == "__main__":
    main()
