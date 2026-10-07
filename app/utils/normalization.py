import math
from typing import Optional


def clamp_score(val: Optional[float], default: float = 0.0) -> float:
    """Clamps a floating point value between 0.0 and 1.0."""
    if val is None or math.isnan(val) or math.isinf(val):
        return default
    return max(0.0, min(1.0, float(val)))


def linear_score(
    x: float,
    min_val: float,
    max_val: float,
    invert: bool = False
) -> float:
    """
    Linearly scales x between min_val and max_val to [0.0, 1.0].
    If invert is True, lower values yield higher scores.
    """
    if math.isnan(x) or math.isinf(x):
        return 0.0

    if max_val <= min_val:
        return 0.5

    norm = (x - min_val) / (max_val - min_val)
    norm = max(0.0, min(1.0, norm))

    return 1.0 - norm if invert else norm


def sigmoid_score(
    x: float,
    center: float,
    slope: float = 1.0
) -> float:
    """
    Smoothly maps x to (0, 1) using a standard logistic sigmoid function.
    center: the input value that maps to 0.5.
    slope: sensitivity (positive = increasing score with x, negative = decreasing).
    """
    if math.isnan(x) or math.isinf(x):
        return 0.5

    try:
        z = slope * (x - center)
        # Prevent overflow in exp
        if z < -40.0:
            return 0.0
        if z > 40.0:
            return 1.0
        return 1.0 / (1.0 + math.exp(-z))
    except OverflowError:
        return 0.0 if slope * (x - center) < 0 else 1.0


def bell_score(
    x: float,
    center: float,
    width: float
) -> float:
    """
    Gaussian bell-shaped curve scoring.
    Highest (1.0) when x == center, decreases symmetrically as |x - center| increases.
    width corresponds to 2 * standard deviations.
    """
    if math.isnan(x) or math.isinf(x) or width <= 0:
        return 0.0

    diff = (x - center) / width
    return math.exp(-0.5 * (diff ** 2))
