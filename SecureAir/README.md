# SecureAir

**Stage 2: local hand detection and landmark extraction.** This is still a research prototype, not a complete authentication system.

## What Stage 2 adds

- MediaPipe Hands processing through `gesture/hand_detector.py`.
- Exactly 21 finite XYZ landmarks validated by `gesture/landmarks.py`.
- Wrist-relative, palm-scale normalization in `gesture/landmarks.py`.
- A camera preview utility that displays transient frames but does not save them.
- Synthetic unit tests that require no webcam.

Normalization subtracts the wrist position from all landmarks, removing image translation, then divides coordinates by the wrist-to-middle-finger MCP distance, reducing apparent hand-size variation. It also scales Z by that same 2D palm measure. This does not correct perspective, rotation, camera calibration, lighting, or all depth errors.

Two hands are detected so that the current one-hand mode can reject ambiguous captures rather than silently choosing a hand. Two-hand authentication is not implemented.

## Windows setup

From the `SecureAir` directory, in PowerShell:

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

Allow camera access when Windows asks. Quit the preview with **Q** or **Esc**. If the camera is unavailable, close apps using it and try `python -m gesture.camera_preview --camera 1`.

The secret is only a local environment setting; never commit it. Camera frames are processed in memory and discarded. Do not use the preview around people without their consent.

## Stage status

Stage 2 implements landmark capture and normalization only. It does **not** recognize gestures, enroll users, train a model, or authenticate. Run tests before proceeding to gesture recognition.
