"""Local hand landmark validation and normalization helpers.

MediaPipe returns 21 image-relative (x, y, z) landmarks. We translate them
relative to the wrist and divide by a palm-size estimate (wrist to middle
finger MCP), reducing dependence on image position and apparent hand size.
This is not camera calibration: perspective, hand rotation and depth estimates
still affect values. Raw frames are not accepted or stored by this module.
"""
from __future__ import annotations

import math
from typing import Sequence

LANDMARK_COUNT = 21
COORDINATE_COUNT = 3
WRIST = 0
MIDDLE_FINGER_MCP = 9


class LandmarkError(ValueError):
    """Raised when a landmark set is malformed or cannot be normalized."""


def validate_landmarks(landmarks: Sequence[Sequence[float]]) -> tuple[tuple[float, float, float], ...]:
    """Return validated immutable 21-point XYZ landmarks; reject NaN/inf and malformed input."""
    if len(landmarks) != LANDMARK_COUNT:
        raise LandmarkError(f"Expected {LANDMARK_COUNT} landmarks; received {len(landmarks)}.")
    points: list[tuple[float, float, float]] = []
    for index, point in enumerate(landmarks):
        if len(point) < COORDINATE_COUNT:
            raise LandmarkError(f"Landmark {index} must contain x, y and z coordinates.")
        xyz = tuple(float(point[axis]) for axis in range(COORDINATE_COUNT))
        if not all(math.isfinite(value) for value in xyz):
            raise LandmarkError(f"Landmark {index} contains a non-finite coordinate.")
        points.append(xyz)
    return tuple(points)


def normalize_landmarks(landmarks: Sequence[Sequence[float]]) -> tuple[float, ...]:
    """Return 63 wrist-relative, palm-scale-normalized XYZ values.

    Translation: subtract wrist coordinates from every point. Scale: divide
    every axis by wrist-to-middle-MCP Euclidean distance in XY. Z is also
    scaled by this palm measure. Reject a near-zero palm scale rather than
    producing unstable huge values. The resulting vector is suitable for later
    feature extraction; it is not yet a trained biometric profile.
    """
    points = validate_landmarks(landmarks)
    wx, wy, wz = points[WRIST]
    mx, my, _ = points[MIDDLE_FINGER_MCP]
    scale = math.hypot(mx - wx, my - wy)
    if scale < 1e-6:
        raise LandmarkError("Cannot normalize landmarks: palm scale is too small.")
    return tuple(
        value
        for x, y, z in points
        for value in ((x - wx) / scale, (y - wy) / scale, (z - wz) / scale)
    )
