# SecureAir

**Stage 4: ordered gesture-sequence tracking.** This is an educational prototype, not a complete authentication system.

## Implemented components

- `gesture/hand_detector.py`: local MediaPipe Hands adapter; no video is saved.
- `gesture/landmarks.py`: validates and normalizes 21 XYZ landmarks relative to the wrist and palm scale.
- `gesture/gesture_recognition.py`: explainable static-pose labels for Open Palm, Fist, Thumbs Up, Victory, and Pointing.
- `gesture/sequence.py`: camera-independent, time-limited sequence state machine. It accepts recognized labels in order, fails on a supported but unexpected pose, and requires a neutral/no-gesture frame before counting the next pose (including repeated gestures).
- Synthetic tests cover landmark, detector, classifier, and sequence behavior without using a webcam.

The classifier assumes an approximately upright hand and has not been evaluated on a real camera dataset. Pose labels and the sequence tracker do not establish identity. There is no enrollment, behavior model, dynamic challenge, or authentication yet.

## Windows setup and tests

From this `SecureAir` directory in PowerShell:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
$env:SECUREAIR_SECRET_KEY = python -c "import secrets; print(secrets.token_hex(32))"
python -m pytest
ruff check .
python -m gesture.camera_preview
```

Quit the preview with **Q** or **Esc**. The preview is optional for unit tests. Frames are transient and processed locally; get consent before camera use. Never commit the environment secret.

See `docs/architecture.md`, `docs/development-plan.md`, and `docs/threat-model.md` for planned architecture, stages, and limitations. The legacy Flask project's test runner deletes its database; run it only against a disposable clone.
