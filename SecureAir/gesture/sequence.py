"""Camera-independent finite-state tracker for ordered gesture sequences.

Feed one recognized label per camera frame to ``step``. A ``None`` label means
no supported gesture is currently visible; it releases the previous pose so a
gesture can be repeated. This module checks order only: it does not capture a
camera, enroll users, authenticate, or assess behavioral biometrics.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import time
from typing import Callable, Iterable

from gesture.gesture_recognition import GESTURES

VALID_GESTURES = frozenset(GESTURES)


@dataclass
class SequenceState:
    """Progress and outcome for one expected sequence."""

    expected: tuple[str, ...]
    timeout_seconds: float
    started_at: float
    captured: list[str] = field(default_factory=list)
    status: str = "IN_PROGRESS"  # IN_PROGRESS, SUCCESS, FAILED, TIMEOUT
    reason: str = "waiting for first gesture"
    last_pose: str | None = None

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-friendly progress snapshot."""
        return {
            "expected_length": len(self.expected),
            "captured": list(self.captured),
            "status": self.status,
            "reason": self.reason,
            "next_gesture_index": len(self.captured),
        }


def create_sequence_state(
    expected: Iterable[str],
    *,
    timeout_seconds: float = 30.0,
    clock: Callable[[], float] = time.monotonic,
) -> SequenceState:
    """Create state after validating a 1–8 gesture expected sequence."""
    sequence = tuple(expected)
    if not 1 <= len(sequence) <= 8:
        raise ValueError("Expected sequence must contain between 1 and 8 gestures.")
    if any(not isinstance(item, str) or item not in VALID_GESTURES for item in sequence):
        raise ValueError("Expected sequence contains an unsupported gesture label.")
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive.")
    return SequenceState(sequence, float(timeout_seconds), clock())


def step_sequence(
    state: SequenceState,
    detected_gesture: str | None,
    *,
    clock: Callable[[], float] = time.monotonic,
) -> SequenceState:
    """Consume one frame label and update the sequence outcome.

    A gesture contributes once while held. The user must show a release/neutral
    frame (``None``) before another gesture is counted, including repetitions.
    Wrong supported gestures fail immediately. Unsupported detector outputs are
    treated as unknown/released rather than as a valid gesture label.
    """
    if state.status != "IN_PROGRESS":
        return state

    if clock() - state.started_at >= state.timeout_seconds:
        state.status = "TIMEOUT"
        state.reason = "sequence timed out"
        state.last_pose = None
        return state

    if detected_gesture is None or detected_gesture not in VALID_GESTURES:
        state.last_pose = None
        if not state.captured:
            state.reason = "waiting for first gesture"
        return state

    # Do not count the same continuously held pose repeatedly.
    if detected_gesture == state.last_pose:
        return state
    state.last_pose = detected_gesture

    expected_gesture = state.expected[len(state.captured)]
    if detected_gesture != expected_gesture:
        state.status = "FAILED"
        state.reason = f"unexpected gesture at position {len(state.captured) + 1}"
        return state

    state.captured.append(detected_gesture)
    if len(state.captured) == len(state.expected):
        state.status = "SUCCESS"
        state.reason = "expected gesture sequence completed"
    else:
        state.reason = "gesture accepted; waiting for release and next gesture"
    return state
