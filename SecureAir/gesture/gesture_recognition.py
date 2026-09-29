"""Explainable geometric classifier for common one-hand poses.

This module recognizes pose shape only. It is not behavioral biometrics, an
identity check, anti-spoofing, or authentication. The upright-camera rules are
intentionally simple and should be evaluated on the target camera/user.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

from gesture.landmarks import LandmarkError, validate_landmarks

GESTURES = ("OPEN_PALM", "FIST", "THUMBS_UP", "VICTORY", "POINTING")

# MediaPipe landmark indices, grouped as thumb, index, middle, ring, pinky.
WRIST = 0
THUMB_MCP, THUMB_IP, THUMB_TIP = 2, 3, 4
FINGER_CHAINS = {
    "index": (5, 6, 8),
    "middle": (9, 10, 12),
    "ring": (13, 14, 16),
    "pinky": (17, 18, 20),
}


@dataclass(frozen=True)
class GestureResult:
    """Pose label and transparent geometric diagnostics; not an auth result."""

    gesture: str | None
    finger_states: dict[str, bool]
    reason: str


def _distance(a: Sequence[float], b: Sequence[float]) -> float:
    return math.dist((a[0], a[1]), (b[0], b[1]))


def _angle_degrees(a: Sequence[float], b: Sequence[float], c: Sequence[float]) -> float:
    """Interior angle ABC in the image plane; returns zero for degenerate joints."""
    ba = (a[0] - b[0], a[1] - b[1])
    bc = (c[0] - b[0], c[1] - b[1])
    denom = math.hypot(*ba) * math.hypot(*bc)
    if denom < 1e-9:
        return 0.0
    cosine = max(-1.0, min(1.0, (ba[0] * bc[0] + ba[1] * bc[1]) / denom))
    return math.degrees(math.acos(cosine))


def _finger_extended(points: Sequence[Sequence[float]], chain: tuple[int, int, int]) -> bool:
    mcp, pip, tip = (points[index] for index in chain)
    wrist = points[WRIST]
    angle = _angle_degrees(mcp, pip, tip)
    # Require both a mostly straight PIP joint and a tip farther from the wrist
    # than the PIP. This is more tolerant than a raw pixel/coordinate threshold.
    return angle >= 145.0 and _distance(tip, wrist) >= _distance(pip, wrist) * 1.05


def _thumb_extended(points: Sequence[Sequence[float]]) -> bool:
    wrist = points[WRIST]
    mcp, ip, tip = points[THUMB_MCP], points[THUMB_IP], points[THUMB_TIP]
    angle = _angle_degrees(mcp, ip, tip)
    return angle >= 135.0 and _distance(tip, wrist) >= _distance(mcp, wrist) * 1.08


def classify_gesture(
    landmarks: Sequence[Sequence[float]] | None,
    handedness: str | None = None,
) -> GestureResult:
    """Classify a single 21-point hand pose; ambiguous inputs return no label.

    The camera is expected to show an approximately upright hand. The thumb-up
    test uses image Y (smaller values are higher). Handedness is accepted for
    future orientation-aware refinement, but the current tests are deliberately
    independent of left/right mirroring.
    """
    del handedness  # Explicitly unused until orientation-aware rules are added.
    if landmarks is None:
        return GestureResult(None, {}, "no hand landmarks")
    try:
        points = validate_landmarks(landmarks)
    except (LandmarkError, TypeError, ValueError) as exc:
        return GestureResult(None, {}, f"invalid landmarks: {exc}")

    states = {name: _finger_extended(points, chain)
              for name, chain in FINGER_CHAINS.items()}
    states["thumb"] = _thumb_extended(points)
    extended = {name for name, value in states.items() if value}

    if len(extended) == 5:
        return GestureResult("OPEN_PALM", states, "all five fingers appear extended")

    non_thumb = {name for name in states if name != "thumb"}
    if not (extended & non_thumb):
        if "thumb" not in extended:
            return GestureResult("FIST", states, "no finger appears extended")
        wrist_y = points[WRIST][1]
        palm_scale = _distance(points[WRIST], points[9])
        if palm_scale > 1e-6 and points[THUMB_TIP][1] < wrist_y - 0.2 * palm_scale:
            return GestureResult("THUMBS_UP", states, "thumb extended above the wrist")
        return GestureResult(None, states, "thumb pose is not clearly pointing upward")

    expected_victory = {"index", "middle"}
    if extended & non_thumb == expected_victory and "thumb" not in extended:
        return GestureResult("VICTORY", states, "index and middle fingers extended")

    if extended & non_thumb == {"index"}:
        return GestureResult("POINTING", states, "index finger extended")

    return GestureResult(None, states, "pose does not match a supported gesture clearly")
