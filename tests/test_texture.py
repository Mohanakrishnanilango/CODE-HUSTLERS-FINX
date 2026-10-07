import numpy as np
import pytest

from app.services.evidence.texture import analyze_texture


def test_texture_normal_contrast():
    # 150x150 image with uniform seabed (value 100) and noisy high-contrast anomaly (values 40-220)
    image = np.full((150, 150), 100, dtype=np.uint8)
    rng = np.random.RandomState(42)
    noise_patch = rng.randint(40, 220, size=(40, 40), dtype=np.uint8)
    image[40:80, 40:80] = noise_patch

    anomaly_mask = np.zeros((150, 150), dtype=np.uint8)
    anomaly_mask[40:80, 40:80] = 255

    res = analyze_texture(image=image, anomaly_mask=anomaly_mask)
    assert res.available is True
    assert res.score is not None
    assert 0.0 <= res.score <= 1.0
    assert "anomaly_glcm" in res.features
    assert "background_glcm" in res.features
    assert res.features["anomaly_glcm"]["contrast"] > 0
    assert "deltas" in res.features


def test_texture_insufficient_pixels():
    image = np.full((100, 100), 120, dtype=np.uint8)
    anomaly_mask = np.zeros((100, 100), dtype=np.uint8)
    # Only 4 pixels
    anomaly_mask[10:12, 10:12] = 255

    res = analyze_texture(image=image, anomaly_mask=anomaly_mask)
    assert res.available is False
    assert res.score is None
    assert "insufficient" in res.reason.lower()
