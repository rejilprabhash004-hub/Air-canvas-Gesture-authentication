"""Enrollment validation, consent, storage and deletion tests; no camera used."""
import json

import pytest

from gesture.enrollment import (
    FEATURE_COUNT,
    EnrollmentError,
    ProfileExistsError,
    delete_profile,
    enroll_profile,
)


def samples(count=10):
    return [[float(sample + feature) / 100 for feature in range(FEATURE_COUNT)]
            for sample in range(count)]


def test_enrollment_requires_explicit_consent(tmp_path):
    with pytest.raises(EnrollmentError, match="consent"):
        enroll_profile(tmp_path, "alice", samples(), consent=False)
    assert not (tmp_path / "profiles").exists()


@pytest.mark.parametrize("count", [9, 21])
def test_enrollment_rejects_sample_counts_outside_range(tmp_path, count):
    with pytest.raises(EnrollmentError, match="10–20"):
        enroll_profile(tmp_path, "alice", samples(count), consent=True)


def test_enrollment_rejects_wrong_length_and_nonfinite_features(tmp_path):
    malformed = samples()
    malformed[0] = [0.0] * (FEATURE_COUNT - 1)
    with pytest.raises(EnrollmentError, match="exactly"):
        enroll_profile(tmp_path, "alice", malformed, consent=True)

    malformed = samples()
    malformed[0][3] = float("nan")
    with pytest.raises(EnrollmentError, match="non-finite"):
        enroll_profile(tmp_path, "alice", malformed, consent=True)


def test_enrollment_saves_only_features_and_delete_removes_profile(tmp_path):
    receipt = enroll_profile(tmp_path, "alice", samples(), consent=True)
    path = tmp_path / "profiles" / "alice.json"
    stored = json.loads(path.read_text(encoding="utf-8"))
    assert receipt["sample_count"] == 10
    assert receipt["encrypted"] is False
    assert stored["samples"] == samples()
    assert "frame" not in stored
    assert delete_profile(tmp_path, "alice") is True
    assert not path.exists()
    assert delete_profile(tmp_path, "alice") is False


def test_existing_profile_is_never_overwritten(tmp_path):
    enroll_profile(tmp_path, "alice", samples(), consent=True)
    with pytest.raises(FileExistsError):
        enroll_profile(tmp_path, "alice", samples(11), consent=True)
    stored = json.loads((tmp_path / "profiles" / "alice.json").read_text())
    assert stored["sample_count"] == 10


def test_profile_id_path_traversal_is_rejected(tmp_path):
    with pytest.raises(EnrollmentError, match="Profile ID"):
        enroll_profile(tmp_path, "../outside", samples(), consent=True)
