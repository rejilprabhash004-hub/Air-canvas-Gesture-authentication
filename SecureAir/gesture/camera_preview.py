"""Local camera preview for manually checking Stage 2 hand landmarks.

Frames are consumed in memory, shown locally, and discarded. Press Q or Escape
to close. This is a diagnostic utility only, not an authentication flow.
"""
from __future__ import annotations

import argparse

from gesture.hand_detector import HandDetector


def run_camera_preview(camera_index: int = 0) -> None:
    """Open the selected local camera and display hand-count/status feedback."""
    import cv2

    capture = cv2.VideoCapture(camera_index)
    if not capture.isOpened():
        capture.release()
        raise RuntimeError(
            f"Could not open camera {camera_index}. Check camera permissions and other apps."
        )
    try:
        with HandDetector(max_hands=2) as detector:
            while True:
                ok, frame = capture.read()
                if not ok:
                    raise RuntimeError("Camera frame could not be read.")
                frame = cv2.flip(frame, 1)
                result = detector.process_frame(frame)
                text = f"{result.status}; hands={result.hand_count}"
                cv2.putText(
                    result.annotated_frame, text, (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (20, 220, 255), 2,
                )
                cv2.imshow("SecureAir local hand preview — Q to quit", result.annotated_frame)
                key = cv2.waitKey(1) & 0xFF
                if key in (ord("q"), 27):
                    break
    finally:
        capture.release()
        cv2.destroyAllWindows()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--camera", type=int, default=0, help="Local camera device index")
    args = parser.parse_args()
    run_camera_preview(args.camera)


if __name__ == "__main__":
    main()
