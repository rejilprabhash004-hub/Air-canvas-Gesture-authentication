"""MediaPipe adapter tests with fake frames/results; no camera is opened."""
from types import SimpleNamespace

import numpy as np
import pytest

from gesture.hand_detector import HandDetector


class FakeHands:
    def __init__(self, result):
        self.result = result
        self.closed = False

    def process(self, _rgb):
        return self.result

    def close(self):
        self.closed = True


class FakeCv2:
    COLOR_BGR2RGB = 1

    @staticmethod
    def cvtColor(frame, _code):
        return frame.copy()


class FakeDrawing:
    @staticmethod
    def draw_landmarks(*_args):
        return None


def make_fake_detector(monkeypatch, hand_count):
    fake_hands = FakeHands(SimpleNamespace(
        multi_hand_landmarks=[
            SimpleNamespace(landmark=[SimpleNamespace(x=i / 20, y=i / 30, z=-i / 100)
                                      for i in range(21)])
            for _ in range(hand_count)
        ],
        multi_handedness=[
            SimpleNamespace(classification=[SimpleNamespace(label="Right")])
            for _ in range(hand_count)
        ],
    ))
    fake_mp = SimpleNamespace(solutions=SimpleNamespace(
        hands=SimpleNamespace(Hands=lambda **_kwargs: fake_hands, HAND_CONNECTIONS=()),
        drawing_utils=FakeDrawing(),
    ))
    monkeypatch.setitem(__import__("sys").modules, "mediapipe", fake_mp)
    monkeypatch.setitem(__import__("sys").modules, "cv2", FakeCv2)
    detector = HandDetector()
    return detector, fake_hands


def test_no_hand_returns_explicit_absence(monkeypatch):
    detector, _ = make_fake_detector(monkeypatch, 0)
    result = detector.process_frame(np.zeros((12, 12, 3), dtype=np.uint8), draw=False)
    assert (result.status, result.hand_count, result.landmarks) == ("no_hand", 0, None)
    detector.close()


def test_one_hand_returns_21_xyz_landmarks_and_handedness(monkeypatch):
    detector, _ = make_fake_detector(monkeypatch, 1)
    result = detector.process_frame(np.zeros((12, 12, 3), dtype=np.uint8), draw=False)
    assert result.status == "ok"
    assert len(result.landmarks) == 21
    assert result.handedness == "Right"
    assert result.annotated_frame is None
    detector.close()


def test_multiple_hands_are_rejected_as_ambiguous(monkeypatch):
    detector, _ = make_fake_detector(monkeypatch, 2)
    result = detector.process_frame(np.zeros((12, 12, 3), dtype=np.uint8), draw=False)
    assert result.status == "multiple_hands"
    assert result.hand_count == 2
    assert result.landmarks is None
    detector.close()


def test_invalid_frames_and_use_after_close_are_rejected(monkeypatch):
    detector, hands = make_fake_detector(monkeypatch, 0)
    with pytest.raises(ValueError):
        detector.process_frame(None)
    detector.close()
    detector.close()
    assert hands.closed
    with pytest.raises(RuntimeError, match="closed"):
        detector.process_frame(np.zeros((5, 5, 3), dtype=np.uint8))
