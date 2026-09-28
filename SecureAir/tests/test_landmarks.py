import math

import pytest

from gesture.landmarks import LandmarkError, normalize_landmarks, validate_landmarks


def sample_points(offset=(0.0, 0.0, 0.0), scale=1.0):
    ox, oy, oz = offset
    # Synthetic, non-collinear 21 points; wrist-to-MCP distance is non-zero.
    return [
        (ox + scale * (i % 5) * 0.1, oy + scale * (i // 5) * 0.1, oz + scale * i * 0.001)
        for i in range(21)
    ]


def test_validates_exactly_21_finite_xyz_points():
    assert len(validate_landmarks(sample_points())) == 21
    with pytest.raises(LandmarkError, match="Expected 21"):
        validate_landmarks(sample_points()[:-1])
    malformed = sample_points()
    malformed[4] = (0.1, 0.2)
    with pytest.raises(LandmarkError, match="x, y and z"):
        validate_landmarks(malformed)
    malformed = sample_points()
    malformed[2] = (math.nan, 0.0, 0.0)
    with pytest.raises(LandmarkError, match="non-finite"):
        validate_landmarks(malformed)


def test_normalization_is_invariant_to_translation_and_uniform_scale():
    reference = normalize_landmarks(sample_points())
    translated = normalize_landmarks(sample_points((3.0, -4.0, 1.5)))
    scaled = normalize_landmarks(sample_points(scale=4.0))
    assert reference == pytest.approx(translated)
    assert reference == pytest.approx(scaled)
    assert len(reference) == 63


def test_rejects_degenerate_palm_scale():
    points = [(0.0, 0.0, 0.0)] * 21
    with pytest.raises(LandmarkError, match="palm scale"):
        normalize_landmarks(points)
