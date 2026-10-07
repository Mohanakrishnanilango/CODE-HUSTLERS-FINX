from typing import Any, Dict, List
from app.services.evidence.fusion import FusionResult


def rank_detections(candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Ranks multiple detected anomaly candidates within a single SSS image
    in descending order of their fused confidence score.

    Each item in candidates is expected to have 'fusion_result' (FusionResult or dict)
    or 'final_confidence'.
    """
    if not candidates:
        return []

    def get_score(c: Dict[str, Any]) -> float:
        if "fusion_result" in c:
            f_res = c["fusion_result"]
            if isinstance(f_res, FusionResult):
                return f_res.final_confidence
            elif isinstance(f_res, dict):
                return float(f_res.get("final_confidence", 0.0))
        return float(c.get("final_confidence", 0.0))

    # Sort descending by confidence score
    sorted_candidates = sorted(candidates, key=get_score, reverse=True)

    # Assign 1-indexed rank
    for rank_idx, cand in enumerate(sorted_candidates, start=1):
        cand["rank"] = rank_idx

    return sorted_candidates
