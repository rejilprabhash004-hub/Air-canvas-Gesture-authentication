"""
Hand landmark detection using MediaPipe.

Uses the mediapipe.solutions.hands API (Legacy/Solutions API), pinned
to mediapipe==0.10.14 in requirements.txt. This is a HARD requirement,
not a suggestion: verified against this environment, mediapipe 0.10.33
(the latest on PyPI at time of writing) removes `mediapipe.solutions`
entirely (AttributeError on import), because it has fully migrated to
the newer mediapipe.tasks Task API. If `pip install mediapipe` is run
without the version pin, this module will break. Worth a one-line
mention in your documentation/viva as evidence of dependency-pinning
discipline (a real secure-development practice, not just academic
box-ticking).
"""

import cv2
import mediapipe as mp
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import Config


class HandDetector:
    """
    Thin wrapper around mp.solutions.hands.Hands.

    Usage:
        detector = HandDetector()
        landmarks, annotated_frame = detector.find_hands(frame)
        detector.close()
    """

    def __init__(self, max_hands: int = 1):
        self.mp_hands = mp.solutions.hands
        self.mp_drawing = mp.solutions.drawing_utils
        self.mp_drawing_styles = mp.solutions.drawing_styles

        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=max_hands,
            min_detection_confidence=Config.MP_DETECTION_CONFIDENCE,
            min_tracking_confidence=Config.MP_TRACKING_CONFIDENCE,
        )

    def find_hands(self, frame_bgr, draw: bool = True):
        """
        Runs detection on a single BGR frame (as returned by cv2.VideoCapture).

        Returns:
            landmark_list: list of (x, y, z) tuples in normalized [0,1]
                            image coordinates for the FIRST detected hand,
                            or None if no hand is detected.
            handedness: "Left" or "Right" (as reported by MediaPipe, which
                        labels from the SUBJECT's perspective — this matters
                        for thumb-direction logic in gesture_recognizer.py),
                        or None if no hand is detected.
            annotated_frame: the input frame with landmarks drawn on it
                              (same frame if draw=False or no hand found).
        """
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        # MediaPipe expects a non-writeable array for performance; this
        # also avoids accidental in-place mutation before drawing.
        frame_rgb.flags.writeable = False
        results = self.hands.process(frame_rgb)
        frame_rgb.flags.writeable = True

        annotated_frame = frame_bgr

        if not results.multi_hand_landmarks:
            return None, None, annotated_frame

        first_hand = results.multi_hand_landmarks[0]
        landmark_list = [(lm.x, lm.y, lm.z) for lm in first_hand.landmark]

        handedness = None
        if results.multi_handedness:
            handedness = results.multi_handedness[0].classification[0].label

        if draw:
            self.mp_drawing.draw_landmarks(
                annotated_frame,
                first_hand,
                self.mp_hands.HAND_CONNECTIONS,
                self.mp_drawing_styles.get_default_hand_landmarks_style(),
                self.mp_drawing_styles.get_default_hand_connections_style(),
            )

        return landmark_list, handedness, annotated_frame

    def close(self):
        self.hands.close()
