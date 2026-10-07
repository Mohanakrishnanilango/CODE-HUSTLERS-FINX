import numpy as np
import pytest

from app.services.evidence.context import analyze_seafloor_context


def test_context_high_contrast():
    # 150x150 image. Background is 60, anomaly is 190.
    image = np.full((150, 150), 60, dtype=np.uint8)
    anomaly_mask = np.zeros((150, 150), dtype=np.uint8)

    image[60:90, 60:90] = 190
    anomaly_mask[60:90, 60:90] = 255

    res = analyze_seafloor_context(image=image, anomaly_mask=anomaly_mask)
    assert res.available is True
    assert res.score is not None
    assert res.score > 0.5
    assert res.features["weber_contrast"] > 1.5
    assert res.features["mean_anomaly_intensity"] == pytest.approx(190.0, abs=1.0)
    assert res.features["mean_background_intensity"] == pytest.approx(60.0, abs=1.0)


def test_context_insufficient_background():
    # Anomaly mask covers almost entire canvas
    image = np.full((50, 50), 100, dtype=np.uint8)
    anomaly_mask = np.full((50, 50), 255, dtype=np.uint8)

    res = analyze_seafloor_context(image=image, anomaly_mask=anomaly_mask)
    assert res.available is False
    assert res.score is None
    assert "insufficient background" in res.reason.lower()
