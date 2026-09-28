"""MediaPipe Hands adapter; all frame processing remains in local memory.

No video or frame is written to disk or transmitted. Authentication mode is
one-hand-only: zero hands is reported as absent, and multiple hands are marked
ambiguous rather than silently selecting the first detected hand.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class HandObservation:
    """Result from one frame. Landmarks are MediaPipe normalized image XYZ."""

    status: str  # "ok", "no_hand", or "multiple_hands"
    landmarks: tuple[tuple[float, float, float], ...] | None
    handedness: str | None
    hand_count: int
    annotated_frame: Any | None = None  # transient in-memory preview only


class HandDetector:
    """Thin local-only wrapper around MediaPipe's Solutions Hands API."""

    def __init__(
        self,
        max_hands: int = 2,
        detection_confidence: float = 0.7,
        tracking_confidence: float = 0.7,
    ) -> None:
        if max_hands < 2:
            raise ValueError("Use max_hands >= 2 so multiple-hand captures can be rejected.")
        for name, value in (("detection_confidence", detection_confidence),
                            ("tracking_confidence", tracking_confidence)):
            if not 0.0 < value <= 1.0:
                raise ValueError(f"{name} must be in (0, 1].")
        try:
            import mediapipe as mp
        except ImportError as exc:
            raise RuntimeError("Install SecureAir requirements to use MediaPipe.") from exc
        if not hasattr(mp, "solutions"):
            raise RuntimeError(
                "This detector requires the pinned MediaPipe Solutions API (0.10.14)."
            )
        self._cv2 = __import__("cv2")
        self._mp_hands = mp.solutions.hands
        self._drawing = mp.solutions.drawing_utils
        self._hands = self._mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=max_hands,
            min_detection_confidence=detection_confidence,
            min_tracking_confidence=tracking_confidence,
        )
        self._closed = False

    def process_frame(self, frame_bgr: Any, *, draw: bool = True) -> HandObservation:
        """Process a BGR frame locally; returned annotation is never persisted."""
        if self._closed:
            raise RuntimeError("HandDetector is closed.")
        if frame_bgr is None or getattr(frame_bgr, "ndim", 0) != 3:
            raise ValueError("Expected a three-dimensional BGR camera frame.")
        if frame_bgr.shape[2] != 3 or frame_bgr.shape[0] == 0 or frame_bgr.shape[1] == 0:
            raise ValueError("Expected a non-empty three-channel BGR frame.")

        rgb = self._cv2.cvtColor(frame_bgr, self._cv2.COLOR_BGR2RGB)
        rgb.flags.writeable = False
        try:
            result = self._hands.process(rgb)
        finally:
            rgb.flags.writeable = True

        hand_list = result.multi_hand_landmarks or []
        count = len(hand_list)
        annotated = frame_bgr.copy() if draw else None
        if draw and annotated is not None:
            for hand in hand_list:
                self._drawing.draw_landmarks(
                    annotated, hand, self._mp_hands.HAND_CONNECTIONS
                )

        if count == 0:
            return HandObservation("no_hand", None, None, 0, annotated)
        if count != 1:
            return HandObservation("multiple_hands", None, None, count, annotated)

        points = tuple((float(point.x), float(point.y), float(point.z))
                       for point in hand_list[0].landmark)
        handedness = None
        classifications = result.multi_handedness or []
        if classifications and classifications[0].classification:
            handedness = classifications[0].classification[0].label
        return HandObservation("ok", points, handedness, 1, annotated)

    def close(self) -> None:
        """Release MediaPipe resources; safe to call more than once."""
        if not self._closed:
            self._hands.close()
            self._closed = True

    def __enter__(self) -> "HandDetector":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
