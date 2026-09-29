"""Consent-based local storage for normalized hand-landmark enrollment samples.

This module accepts already-normalized feature vectors, never camera frames. The
profile JSON is sensitive biometric-derived data and is not encrypted; restrict
access to the local data directory and do not sync it to shared/cloud storage.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import re
from typing import Sequence

from gesture.landmarks import COORDINATE_COUNT, LANDMARK_COUNT

FEATURE_COUNT = LANDMARK_COUNT * COORDINATE_COUNT
MIN_SAMPLES = 10
MAX_SAMPLES = 20
PROFILE_VERSION = 1
_PROFILE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")


class EnrollmentError(ValueError):
    """Raised when enrollment consent or input data is invalid."""


class ProfileExistsError(FileExistsError):
    """Raised rather than overwriting an existing enrolled profile."""


def _validated_samples(samples: Sequence[Sequence[float]]) -> list[list[float]]:
    if not MIN_SAMPLES <= len(samples) <= MAX_SAMPLES:
        raise EnrollmentError(f"Enrollment requires {MIN_SAMPLES}–{MAX_SAMPLES} samples.")
    validated: list[list[float]] = []
    for sample_index, sample in enumerate(samples):
        if len(sample) != FEATURE_COUNT:
            raise EnrollmentError(
                f"Sample {sample_index + 1} must contain exactly {FEATURE_COUNT} features."
            )
        vector = [float(value) for value in sample]
        if not all(math.isfinite(value) for value in vector):
            raise EnrollmentError(f"Sample {sample_index + 1} contains a non-finite feature.")
        validated.append(vector)
    return validated


def _profile_path(data_dir: Path, profile_id: str) -> Path:
    if not isinstance(profile_id, str) or not _PROFILE_ID.fullmatch(profile_id):
        raise EnrollmentError("Profile ID must be 1–64 letters, numbers, underscores, or hyphens.")
    return data_dir / "profiles" / f"{profile_id}.json"


def enroll_profile(
    data_dir: str | Path,
    profile_id: str,
    samples: Sequence[Sequence[float]],
    *,
    consent: bool,
) -> dict[str, object]:
    """Save 10–20 normalized vectors only after explicit affirmative consent.

    The resulting local JSON contains sensitive biometric-derived data and is
    plaintext. Creation uses exclusive file creation to avoid replacing an
    existing profile. File permissions are restricted on POSIX systems where
    supported; callers remain responsible for securing the host and backups.
    """
    if consent is not True:
        raise EnrollmentError("Explicit consent is required before profile enrollment.")
    vectors = _validated_samples(samples)
    root = Path(data_dir).expanduser()
    path = _profile_path(root, profile_id)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    payload = {
        "version": PROFILE_VERSION,
        "profile_id": profile_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "sample_count": len(vectors),
        "feature_count": FEATURE_COUNT,
        "samples": vectors,
    }
    encoded = json.dumps(payload, separators=(",", ":"), allow_nan=False).encode("utf-8")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    try:
        descriptor = os.open(path, flags, 0o600)
    except FileExistsError as exc:
        raise ProfileExistsError(f"A profile already exists for {profile_id!r}.") from exc
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(encoded)
            output.flush()
            os.fsync(output.fileno())
    except Exception:
        try:
            path.unlink(missing_ok=True)
        finally:
            raise
    return {
        "profile_id": profile_id,
        "sample_count": len(vectors),
        "feature_count": FEATURE_COUNT,
        "created_at": payload["created_at"],
        "encrypted": False,
    }


def delete_profile(data_dir: str | Path, profile_id: str) -> bool:
    """Delete one local profile; return False when it did not exist."""
    path = _profile_path(Path(data_dir).expanduser(), profile_id)
    try:
        path.unlink()
    except FileNotFoundError:
        return False
    return True
