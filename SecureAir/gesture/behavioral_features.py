"""Extract simple temporal motion summaries from timestamped hand landmarks.

Input is a sequence of (timestamp_seconds, 21 XYZ landmarks) pairs. Each frame is
validated, checked for image-boundary violations, and normalized by palm scale.
This produces interpretable motion features only; it is not a trained model or
an identity/authentication decision. Raw frames are never accepted or stored.
"""
from __future__ import annotations

import math
from typing import Sequence

from gesture.landmarks import LandmarkError, normalize_landmarks, validate_landmarks


class BehavioralFeatureError(ValueError):
    """Raised when a temporal landmark sequence is invalid or out of frame."""


def extract_behavioral_features(
    frames: Sequence[tuple[float, Sequence[Sequence[float]]]],
) -> dict[str, float]:
    """Return palm-normalized motion summaries for an ordered sequence.

    At least two timestamped frames are required. Timestamps must be finite,
    numeric, and strictly increasing. Image-relative x/y coordinates must lie
    within [0, 1]; MediaPipe z is depth-relative and is only checked for
    finiteness by landmark validation. For each frame, wrist translation is
    removed and XYZ coordinates are scaled by that frame's palm size. Adjacent
    Euclidean changes then yield speeds in palm-lengths per second.

    Returned metrics are duration, mean/peak speed, mean acceleration, total
    path length, endpoint displacement, and path efficiency. Acceleration is
    zero for exactly two frames; path efficiency is zero for a stationary path.
    """
    if len(frames) < 2:
        raise BehavioralFeatureError("At least two timestamped frames are required.")

    times: list[float] = []
    normalized_frames: list[tuple[float, ...]] = []
    for index, frame in enumerate(frames):
        if len(frame) != 2:
            raise BehavioralFeatureError(f"Frame {index + 1} must be (timestamp, landmarks).")
        timestamp, landmarks = frame
        if isinstance(timestamp, bool) or not isinstance(timestamp, (int, float)):
            raise BehavioralFeatureError(f"Timestamp {index + 1} must be numeric.")
        timestamp = float(timestamp)
        if not math.isfinite(timestamp):
            raise BehavioralFeatureError(f"Timestamp {index + 1} must be finite.")
        if times and timestamp <= times[-1]:
            raise BehavioralFeatureError("Frame timestamps must be strictly increasing.")
        try:
            points = validate_landmarks(landmarks)
        except (LandmarkError, TypeError, ValueError) as exc:
            raise BehavioralFeatureError(f"Invalid landmarks in frame {index + 1}: {exc}") from exc
        for point_index, (x, y, _z) in enumerate(points):
            if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
                raise BehavioralFeatureError(
                    f"Landmark {point_index} in frame {index + 1} is outside image bounds."
                )
        try:
            normalized_frames.append(normalize_landmarks(points))
        except LandmarkError as exc:
            raise BehavioralFeatureError(f"Cannot normalize frame {index + 1}: {exc}") from exc
        times.append(timestamp)

    speeds: list[float] = []
    path_length = 0.0
    for index in range(1, len(normalized_frames)):
        elapsed = times[index] - times[index - 1]
        squared_delta = sum(
            (current - previous) ** 2
            for current, previous in zip(normalized_frames[index], normalized_frames[index - 1])
        )
        distance = math.sqrt(squared_delta / 21.0)
        speeds.append(distance / elapsed)
        path_length += distance

    accelerations = [
        abs(speeds[index] - speeds[index - 1]) / (times[index + 1] - times[index - 1])
        for index in range(1, len(speeds))
    ]
    start, end = normalized_frames[0], normalized_frames[-1]
    displacement = math.sqrt(sum((b - a) ** 2 for a, b in zip(start, end)) / 21.0)
    mean_speed = sum(speeds) / len(speeds)
    duration = times[-1] - times[0]

    return {
        "duration_seconds": duration,
        "mean_speed_palm_per_second": mean_speed,
        "peak_speed_palm_per_second": max(speeds),
        "mean_acceleration_palm_per_second_squared": (
            sum(accelerations) / len(accelerations) if accelerations else 0.0
        ),
        "path_length_palm_units": path_length,
        "endpoint_displacement_palm_units": displacement,
        "path_efficiency": displacement / path_length if path_length > 1e-12 else 0.0,
    }
