import numpy as np
import pytest

from app.schemas.survey import SurveyMetadata
from app.services.evidence.size import analyze_size


def test_size_with_resolution():
    mask = np.zeros((100, 100), dtype=np.uint8)
    mask[20:60, 30:70] = 255  # 40x40 px = 1600 px area

    metadata = SurveyMetadata(resolution_m_per_pixel=0.10)
    res = analyze_size(mask=mask, bbox=(30, 20, 40, 40), metadata=metadata)

    assert res.available is True
    assert res.score is not None
    assert res.features["physical_size_calculated"] is True
    assert res.features["width_meters"] == pytest.approx(4.0, rel=1e-2)
    assert res.features["height_meters"] == pytest.approx(4.0, rel=1e-2)
    assert res.features["area_sq_meters"] == pytest.approx(16.0, rel=1e-2)


def test_size_missing_resolution_marks_unavailable():
    mask = np.zeros((100, 100), dtype=np.uint8)
    mask[20:60, 30:70] = 255

    res = analyze_size(mask=mask, bbox=(30, 20, 40, 40), metadata=None, require_physical=True)

    # Missing resolution -> unavailable -> triggers dynamic weight redistribution
    assert res.available is False
    assert res.score is None
    assert res.features["physical_size_calculated"] is False
    assert res.features["width_meters"] is None
    assert "spatial resolution metadata" in res.reason.lower()
