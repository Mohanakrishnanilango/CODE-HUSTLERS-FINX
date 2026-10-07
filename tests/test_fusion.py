import pytest
from app.schemas.evidence import CompleteEvidenceSet, EvidenceResult
from app.services.evidence.fusion import fuse_evidence
from app.services.priority.ranker import rank_detections


def test_fusion_all_modalities_available():
    ev_set = CompleteEvidenceSet(
        shape=EvidenceResult(available=True, score=0.80, features={}),
        texture=EvidenceResult(available=True, score=0.70, features={}),
        shadow=EvidenceResult(available=True, score=0.90, features={}),
        size=EvidenceResult(available=True, score=0.60, features={}),
        context=EvidenceResult(available=True, score=0.85, features={}),
    )

    res = fuse_evidence(anomaly_score=0.90, evidence_set=ev_set)

    assert res.final_confidence > 0.70
    assert res.priority == "HIGH"
    assert res.confidence_percentage == pytest.approx(res.final_confidence * 100.0, abs=0.01)
    assert res.modality_breakdown["size"]["status"] == "INCLUDED"


def test_fusion_dynamic_redistribution_missing_size():
    # Size is marked unavailable (e.g., missing resolution)
    ev_set = CompleteEvidenceSet(
        shape=EvidenceResult(available=True, score=0.80, features={}),
        texture=EvidenceResult(available=True, score=0.70, features={}),
        shadow=EvidenceResult(available=True, score=0.90, features={}),
        size=EvidenceResult(available=False, score=None, features={}, reason="Resolution missing"),
        context=EvidenceResult(available=True, score=0.85, features={}),
    )

    res = fuse_evidence(anomaly_score=0.90, evidence_set=ev_set)

    # Size should be excluded, not penalized with 0
    assert res.modality_breakdown["size"]["status"] == "EXCLUDED_REDISTRIBUTED"
    assert "size" not in res.active_weights
    # Sum of active weights should equal 1.0
    assert sum(res.active_weights.values()) == pytest.approx(1.0, abs=1e-3)
    # Score should be high because all active modalities had high scores
    assert res.final_confidence >= 0.75
    assert res.priority == "HIGH"


def test_priority_ranking_order():
    candidates = [
        {"id": "c1", "final_confidence": 0.45},
        {"id": "c2", "final_confidence": 0.88},
        {"id": "c3", "final_confidence": 0.22},
    ]

    ranked = rank_detections(candidates)

    assert ranked[0]["id"] == "c2"
    assert ranked[0]["rank"] == 1
    assert ranked[1]["id"] == "c1"
    assert ranked[1]["rank"] == 2
    assert ranked[2]["id"] == "c3"
    assert ranked[2]["rank"] == 3
