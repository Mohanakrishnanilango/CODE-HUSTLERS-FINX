import numpy as np
import cv2
import pytest

from app.services.evidence.shape import analyze_shape


def test_shape_normal_irregular_region():
    # Create an irregular elongated shape on a 200x200 canvas
    mask = np.zeros((200, 200), dtype=np.uint8)
    pts = np.array([
        [80, 50], [130, 45], [160, 80], [140, 120],
        [90, 140], [60, 110], [50, 70]
    ], dtype=np.int32)
    cv2.fillPoly(mask, [pts], 255)

    res = analyze_shape(mask, image_shape=(200, 200), min_area_px=15)
    assert res.available is True
    assert res.score is not None
    assert 0.0 <= res.score <= 1.0
    assert res.features["area"] > 0
    assert res.features["perimeter"] > 0
    assert res.features["circularity"] < 1.0
    assert res.features["is_border_touching"] is False
    assert len(res.features["hu_moments"]) == 7


def test_shape_empty_mask():
    mask = np.zeros((100, 100), dtype=np.uint8)
    res = analyze_shape(mask, image_shape=(100, 100))
    assert res.available is False
    assert res.score is None
    assert "empty" in res.reason.lower()


def test_shape_tiny_region():
    mask = np.zeros((100, 100), dtype=np.uint8)
    # Only 3 pixels
    mask[50, 50] = 255
    mask[50, 51] = 255
    mask[51, 50] = 255

    res = analyze_shape(mask, image_shape=(100, 100), min_area_px=10)
    assert res.available is False
    assert res.score is None
    assert "minimum threshold" in res.reason.lower()


def test_shape_border_touching():
    mask = np.zeros((100, 100), dtype=np.uint8)
    # Rectangle right against top-left margin
    mask[0:30, 0:30] = 255

    res = analyze_shape(mask, image_shape=(100, 100), min_area_px=10)
    assert res.available is True
    assert res.features["is_border_touching"] is True
    assert "touches image margin" in res.reason.lower()
