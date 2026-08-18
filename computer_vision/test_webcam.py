"""
Standalone sanity check for the webcam + MediaPipe pipeline.
Run this BEFORE wiring gesture recognition into the Flask app, so any
camera/driver issues are isolated from the rest of the system.

Run:  python computer_vision/test_webcam.py
Quit: press 'q' with the window focused.
"""

import cv2
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from computer_vision.hand_detector import HandDetector
from computer_vision.gesture_recognizer import classify_gesture


def main():
    cap = cv2.VideoCapture(0)  # 0 = default webcam

    if not cap.isOpened():
        print("[ERROR] Could not open webcam (index 0). "
              "Check that no other application is using it, and that "
              "camera permissions are granted for this Python process.")
        return

    detector = HandDetector(max_hands=1)
    print("Webcam opened. Press 'q' in the window to quit.")

    while True:
        success, frame = cap.read()
        if not success:
            print("[ERROR] Failed to read frame from webcam.")
            break

        frame = cv2.flip(frame, 1)  # mirror for a natural "selfie" view
        landmarks, handedness, annotated = detector.find_hands(frame)

        gesture = classify_gesture(landmarks, handedness) if landmarks else None

        status_text = f"Hand detected: {'YES' if landmarks else 'NO'}"
        cv2.putText(
            annotated, status_text, (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX, 0.8,
            (0, 255, 0) if landmarks else (0, 0, 255), 2,
        )
        gesture_text = f"Gesture: {gesture if gesture else '-'}"
        cv2.putText(
            annotated, gesture_text, (10, 65),
            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 200, 0), 2,
        )

        cv2.imshow("Hand Detection Test - press q to quit", annotated)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    detector.close()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
