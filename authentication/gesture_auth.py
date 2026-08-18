"""
Gesture authentication: builds a live gesture sequence from webcam
frames and compares it against a user's registered sequence.

Split into two layers:
  1. Pure state-machine logic (GestureAuthState + step()) — no camera,
     no threading, fully unit-testable.
  2. GestureAuthManager — wraps (1) in a background thread that reads
     the webcam, classifies each frame, and feeds detected gestures
     into step(). The Flask app talks to the manager, not to OpenCV
     directly.

Design note: this app supports ONE active gesture-auth session at a
time (single shared webcam, single demo user) — appropriate for an
academic single-machine demo. A production multi-user system would
need per-session camera handling, which is out of scope here and
worth naming explicitly as a limitation in your documentation.
"""

import time
import threading
import cv2
import sys
import os
from datetime import datetime, timedelta

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import Config
from computer_vision.hand_detector import HandDetector
from computer_vision.gesture_recognizer import classify_gesture

# How many consecutive frames a gesture must hold steady before it
# counts as "performed" (filters out transitional/jittery poses).
STABLE_FRAMES_REQUIRED = 10

# Overall time limit for completing the sequence before we give up.
CAPTURE_TIMEOUT_SECONDS = 30


class GestureAuthState:
    """Plain data holder for one gesture-auth attempt's progress."""

    def __init__(self, expected_sequence):
        self.expected_sequence = list(expected_sequence)
        self.captured_sequence = []
        self.current_gesture = None       # this frame's raw classification
        self.stable_gesture = None        # gesture being held right now
        self.stable_count = 0
        self.last_appended_gesture = None
        self.status = "IN_PROGRESS"       # IN_PROGRESS | GRANTED | DENIED | TIMEOUT
        self.started_at = datetime.now()

    def to_dict(self):
        return {
            "current_gesture": self.current_gesture,
            "captured_sequence": self.captured_sequence,
            "expected_length": len(self.expected_sequence),
            "status": self.status,
        }


def step(state: GestureAuthState, detected_gesture):
    """
    Advances the state machine by exactly one frame's classification
    result. Pure function (mutates state, no I/O) — this is what unit
    tests exercise directly, without any camera involved.
    """
    if state.status != "IN_PROGRESS":
        return  # already resolved; ignore further frames

    if (datetime.now() - state.started_at) > timedelta(seconds=CAPTURE_TIMEOUT_SECONDS):
        state.status = "TIMEOUT"
        return

    state.current_gesture = detected_gesture

    if detected_gesture is None:
        # Hand removed / ambiguous pose — resets stability tracking so
        # the SAME gesture can be deliberately repeated later if the
        # user drops their hand between repeats.
        state.stable_gesture = None
        state.stable_count = 0
        state.last_appended_gesture = None
        return

    if detected_gesture == state.stable_gesture:
        state.stable_count += 1
    else:
        state.stable_gesture = detected_gesture
        state.stable_count = 1

    if state.stable_count == STABLE_FRAMES_REQUIRED and \
       detected_gesture != state.last_appended_gesture:
        state.captured_sequence.append(detected_gesture)
        state.last_appended_gesture = detected_gesture

        expected_so_far = state.expected_sequence[:len(state.captured_sequence)]
        if state.captured_sequence != expected_so_far:
            state.status = "DENIED"
            return

        if len(state.captured_sequence) == len(state.expected_sequence):
            state.status = "GRANTED"


class GestureAuthManager:
    """
    Owns the webcam + background capture thread for the single active
    gesture-auth attempt. Thread-safe access via self._lock.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._thread = None
        self._running = False
        self._state = None
        self._latest_frame = None  # for MJPEG streaming

    def start(self, expected_sequence):
        self.stop()  # ensure any previous session/thread is cleaned up
        with self._lock:
            self._state = GestureAuthState(expected_sequence)
            self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2)
        self._thread = None

    def get_status(self):
        with self._lock:
            if self._state is None:
                return {"current_gesture": None, "captured_sequence": [],
                         "expected_length": 0, "status": "NOT_STARTED"}
            return self._state.to_dict()

    def get_latest_jpeg(self):
        with self._lock:
            return self._latest_frame

    def _capture_loop(self):
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            with self._lock:
                if self._state is not None:
                    self._state.status = "DENIED"
            print("[gesture_auth] ERROR: could not open webcam.")
            return

        detector = HandDetector(max_hands=1)

        try:
            while self._running:
                success, frame = cap.read()
                if not success:
                    time.sleep(0.05)
                    continue

                frame = cv2.flip(frame, 1)
                landmarks, handedness, annotated = detector.find_hands(frame)
                gesture = classify_gesture(landmarks, handedness) if landmarks else None

                with self._lock:
                    if self._state is not None:
                        step(self._state, gesture)
                        status = self._state.status
                    else:
                        status = "NOT_STARTED"

                label = f"Gesture: {gesture or '-'}"
                cv2.putText(annotated, label, (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 200, 0), 2)
                ok, buf = cv2.imencode(".jpg", annotated)
                if ok:
                    with self._lock:
                        self._latest_frame = buf.tobytes()

                if status != "IN_PROGRESS":
                    break

                time.sleep(0.03)  # ~30fps cap
        finally:
            detector.close()
            cap.release()


# Module-level singleton — one active gesture-auth session app-wide,
# matching the single-webcam/single-demo-user scope described above.
gesture_auth_manager = GestureAuthManager()
