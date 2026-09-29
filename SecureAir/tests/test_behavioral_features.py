"""Synthetic tests for palm-normalized behavioral feature extraction."""
import pytest

from gesture.behavioral_features import (
    BehavioralFeatureError,
    extract_behavioral_features,
)


def landmarks(offset=0.0, scale=1.0):
    """Make a simple valid 21-point hand, translating all XY points by offset."""
    points = [(0.5 + offset, 0.75, 0.0) for _ in range(21)]
    points[0] = (0.5 + offset, 0.8, 0.0)
    points[9] = (0.5 + offset, 0.5, 0.0)
    for index, x, y in [
        (1, -0.03, -0.05), (2, -0.06, -0.10), (3, -0.08, -0.15), (4, -0.10, -0.20),
        (5, -0.07, -0.15), (6, -0.07, -0.30), (7, -0.07, -0.40), (8, -0.07, -0.50),
        (10, 0.00, -0.10), (11, 0.00, -0.30), (12, 0.00, -0.45),
        (13, 0.07, -0.15), (14, 0.07, -0.28), (15, 0.07, -0.37), (16, 0.07, -0.44),
        (17, 0.14, -0.15), (18, 0.14, -0.25), (19, 0.14, -0.31), (20, 0.14, -0.36),
    ]:
        points[index] = (0.5 + offset + x * scale, 0.8 + y * scale, 0.0)
    return points


def test_stationary_sequence_has_zero_motion_and_finite_features():
    frame = landmarks()
    result = extract_behavioral_features([(1.0, frame), (2.0, frame)])
    assert result["duration_seconds"] == 1.0
    assert result["mean_speed_palm_per_second"] == pytest.approx(0.0)
    assert result["peak_speed_palm_per_second"] == pytest.approx(0.0)
    assert result["path_efficiency"] == 0.0
    assert all(value == value and abs(value) != float("inf") for value in result.values())


def test_translation_and_uniform_apparent_scale_are_normalized():
    baseline = extract_behavioral_features([
        (0.0, landmarks()), (1.0, landmarks(offset=0.03)),
    ])
    translated = extract_behavioral_features([
        (0.0, landmarks(offset=0.1)), (1.0, landmarks(offset=0.13)),
    ])
    assert translated["mean_speed_palm_per_second"] == pytest.approx(
        baseline["mean_speed_palm_per_second"], abs=1e-8
    )
    assert translated["path_length_palm_units"] == pytest.approx(
        baseline["path_length_palm_units"], abs=1e-8
    )


def test_constant_velocity_and_acceleration_summary():
    result = extract_behavioral_features([
        (0.0, landmarks()), (1.0, landmarks(offset=0.02)), (2.0, landmarks(offset=0.04)),
    ])
    assert result["mean_speed_palm_per_second"] > 0
    assert result["peak_speed_palm_per_second"] == pytest.approx(
        result["mean_speed_palm_per_second"]
    )
    assert result["mean_acceleration_palm_per_second_squared"] == pytest.approx(0.0, abs=1e-8)
    assert result["path_efficiency"] == pytest.approx(1.0, abs=1e-7)


@pytest.mark.parametrize("frames", [[], [(0.0, landmarks())]])
def test_requires_at_least_two_frames(frames):
    with pytest.raises(BehavioralFeatureError, match="At least two"):
        extract_behavioral_features(frames)


def test_rejects_duplicate_or_nonfinite_timestamps():
    with pytest.raises(BehavioralFeatureError, match="strictly increasing"):
        extract_behavioral_features([(0.0, landmarks()), (0.0, landmarks())])
    with pytest.raises(BehavioralFeatureError, match="finite"):
        extract_behavioral_features([(0.0, landmarks()), (float("nan"), landmarks())])


def test_rejects_out_of_frame_and_malformed_landmarks():
    outside = landmarks()
    outside[3] = (1.1, 0.2, 0.0)
    with pytest.raises(BehavioralFeatureError, match="outside image bounds"):
        extract_behavioral_features([(0.0, landmarks()), (1.0, outside)])
    with pytest.raises(BehavioralFeatureError, match="Invalid landmarks"):
        extract_behavioral_features([(0.0, landmarks()), (1.0, [(0.0, 0.0, 0.0)])])


def test_rejects_degenerate_palm_scale():
    degenerate = [(0.5, 0.5, 0.0)] * 21
    with pytest.raises(BehavioralFeatureError, match="Cannot normalize"):
        extract_behavioral_features([(0.0, landmarks()), (1.0, degenerate)])
