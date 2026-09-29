"""Tests for sequence ordering, release, repetition and timeout behavior."""
import pytest

from gesture.sequence import create_sequence_state, step_sequence


class FakeClock:
    def __init__(self):
        self.value = 100.0

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += seconds


def feed(state, labels, clock):
    for label in labels:
        step_sequence(state, label, clock=clock)
    return state


def test_correct_sequence_requires_neutral_release_between_poses():
    clock = FakeClock()
    state = create_sequence_state(["OPEN_PALM", "FIST", "VICTORY"], clock=clock)
    feed(state, ["OPEN_PALM", "OPEN_PALM", None, "FIST", None, "VICTORY"], clock)
    assert state.status == "SUCCESS"
    assert state.captured == ["OPEN_PALM", "FIST", "VICTORY"]


def test_wrong_gesture_fails_at_first_mismatch():
    clock = FakeClock()
    state = create_sequence_state(["OPEN_PALM", "FIST"], clock=clock)
    feed(state, ["OPEN_PALM", None, "POINTING"], clock)
    assert state.status == "FAILED"
    assert state.captured == ["OPEN_PALM"]
    assert "position 2" in state.reason


def test_repeating_same_gesture_requires_a_release_frame():
    clock = FakeClock()
    state = create_sequence_state(["FIST", "FIST"], clock=clock)
    feed(state, ["FIST", "FIST", "FIST"], clock)
    assert state.status == "IN_PROGRESS"
    assert state.captured == ["FIST"]
    step_sequence(state, None, clock=clock)
    step_sequence(state, "FIST", clock=clock)
    assert state.status == "SUCCESS"


def test_incomplete_sequence_times_out():
    clock = FakeClock()
    state = create_sequence_state(["OPEN_PALM", "FIST"], timeout_seconds=3, clock=clock)
    step_sequence(state, "OPEN_PALM", clock=clock)
    clock.advance(3)
    step_sequence(state, None, clock=clock)
    assert state.status == "TIMEOUT"
    assert state.reason == "sequence timed out"


@pytest.mark.parametrize("expected, timeout", [([], 5), (["UNKNOWN"], 5), (["FIST"], 0)])
def test_invalid_sequence_configuration_is_rejected(expected, timeout):
    with pytest.raises(ValueError):
        create_sequence_state(expected, timeout_seconds=timeout)


def test_terminal_state_ignores_later_frames():
    clock = FakeClock()
    state = create_sequence_state(["OPEN_PALM"], clock=clock)
    step_sequence(state, "OPEN_PALM", clock=clock)
    step_sequence(state, "FIST", clock=clock)
    assert state.status == "SUCCESS"
    assert state.captured == ["OPEN_PALM"]
