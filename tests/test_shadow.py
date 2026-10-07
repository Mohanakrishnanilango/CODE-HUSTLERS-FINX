import numpy as np
import pytest

from app.schemas.survey import SurveyMetadata
from app.services.evidence.shadow import analyze_shadow, determine_shadow_direction


def test_shadow_detection_with_nadir_metadata():
    # 200x200 image. Nadir at col 100.
    # Anomaly at (120, 50), size (20, 20) -> starboard side (x > 100) -> shadow to the right
    image = np.full((200, 200), 120, dtype=np.uint8)
    anomaly_mask = np.zeros((200, 200), dtype=np.uint8)

    # Anomaly highlight: bright pixels
    image[50:70, 120:140] = 220
    anomaly_mask[50:70, 120:140] = 255

    # Acoustic shadow: dark pixels directly to the right (x=140 to 170)
    image[50:70, 140:170] = 10

    metadata = SurveyMetadata(nadir_column=100)
    res, shadow_mask = analyze_shadow(
        image=image,
        anomaly_mask=anomaly_mask,
        bbox=(120, 50, 20, 20),
        metadata=metadata,
        direction_mode="metadata_based"
    )

    assert res.available is True
    assert res.score is not None
    assert res.score > 0.0
    assert res.features["shadow_detected"] is True
    assert res.features["direction"] == "right"
    assert shadow_mask is not None
    assert np.count_nonzero(shadow_mask) > 0


def test_shadow_missing_metadata_no_fabrication():
    # Mode is metadata_based, but no nadir or channel metadata provided
    image = np.full((200, 200), 120, dtype=np.uint8)
    anomaly_mask = np.zeros((200, 200), dtype=np.uint8)
    anomaly_mask[50:70, 120:140] = 255

    res, shadow_mask = analyze_shadow(
        image=image,
        anomaly_mask=anomaly_mask,
        bbox=(120, 50, 20, 20),
        metadata=None,  # No metadata!
        direction_mode="metadata_based"
    )

    # Must NOT fabricate direction or score
    assert res.available is False
    assert res.score is None
    assert "insufficient sonar geometry" in res.reason.lower()


def test_shadow_no_shadow_present():
    # Background is uniform, no dark dropouts
    image = np.full((200, 200), 120, dtype=np.uint8)
    anomaly_mask = np.zeros((200, 200), dtype=np.uint8)
    anomaly_mask[50:70, 120:140] = 255

    metadata = SurveyMetadata(nadir_column=100)
    res, shadow_mask = analyze_shadow(
        image=image,
        anomaly_mask=anomaly_mask,
        bbox=(120, 50, 20, 20),
        metadata=metadata,
        direction_mode="metadata_based"
    )

    assert res.available is True
    assert res.score == 0.0
    assert res.features["shadow_detected"] is False
