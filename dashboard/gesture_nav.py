"""
Gesture-based dashboard navigation.

Unlike authentication/gesture_auth.py (which matches a fixed SEQUENCE
once, then stops), this runs CONTINUOUSLY while the user has gesture
navigation enabled: each distinct held gesture becomes one "command"
that the frontend consumes and acts on, and the loop keeps running
until the user disables it or the FIST (lock) gesture fires.

Same stability-then-reset pattern as gesture_auth.py: a gesture must
be held for STABLE_FRAMES_REQUIRED_NAV frames to count, and the hand
must be removed (gesture -> None) before the SAME gesture can trigger
again — this lets a held pose not spam-repeat while making repeated
"next page" taps intentional.
"""

import time
import threading
import cv2
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from computer_vision.hand_detector import HandDetector
from computer_vision.gesture_recognizer import classify_gesture

STABLE_FRAMES_REQUIRED_NAV = 10


class NavState:
    def __init__(self):
        self.current_gesture = None
        self.stable_gesture = None
        self.stable_count = 0
        self.last_triggered_gesture = None
        self.pending_action = None  # set when a new command fires; consumed by the status endpoint


def nav_step(state: NavState, detected_gesture):
    """Pure per-frame state update — same testable-without-a-camera pattern as gesture_auth.step()."""
    state.current_gesture = detected_gesture

    if detected_gesture is None:
        state.stable_gesture = None
        state.stable_count = 0
        state.last_triggered_gesture = None
        return

    if detected_gesture == state.stable_gesture:
        state.stable_count += 1
    else:
        state.stable_gesture = detected_gesture
        state.stable_count = 1

    if state.stable_count == STABLE_FRAMES_REQUIRED_NAV and \
       detected_gesture != state.last_triggered_gesture:
        state.pending_action = detected_gesture
        state.last_triggered_gesture = detected_gesture


class NavigationManager:
    """Threaded webcam owner for continuous gesture navigation. Singleton, like gesture_auth_manager."""

    def __init__(self):
        self._lock = threading.Lock()
        self._thread = None
        self._running = False
        self._state = None
        self._latest_frame = None

    def start(self):
        if self._running:
            return  # already running — idempotent
        with self._lock:
            self._state = NavState()
            self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2)
        self._thread = None
        with self._lock:
            self._state = None
            self._latest_frame = None

    def is_running(self):
        return self._running

    def get_and_clear_status(self):
        """
        Returns {"current_gesture", "pending_action"} and CLEARS
        pending_action atomically, so each command is consumed exactly
        once regardless of polling timing/races on the client.
        """
        with self._lock:
            if self._state is None:
                return {"current_gesture": None, "pending_action": None, "running": False}
            action = self._state.pending_action
            self._state.pending_action = None
            return {
                "current_gesture": self._state.current_gesture,
                "pending_action": action,
                "running": True,
            }

    def get_latest_jpeg(self):
        with self._lock:
            return self._latest_frame

    def _capture_loop(self):
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            print("[gesture_nav] ERROR: could not open webcam.")
            self._running = False
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
                        nav_step(self._state, gesture)

                label = f"Nav Gesture: {gesture or '-'}"
                cv2.putText(annotated, label, (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 220, 255), 2)
                ok, buf = cv2.imencode(".jpg", annotated)
                if ok:
                    with self._lock:
                        self._latest_frame = buf.tobytes()

                time.sleep(0.03)
        finally:
            detector.close()
            cap.release()


nav_manager = NavigationManager()
