# SecureAir

**Stage 3: basic geometric gesture recognition.** This is still an educational research prototype, not a complete authentication system.

## What is implemented

- MediaPipe Hands processing through `gesture/hand_detector.py`.
- Validation and wrist-relative, palm-scale normalization of 21 XYZ landmarks in `gesture/landmarks.py`.
- Explainable geometric classification for Open Palm, Fist, Thumbs Up, Victory, and Pointing in `gesture/gesture_recognition.py`.
- Synthetic tests for supported poses, malformed/absent landmarks, and ambiguous poses.
- Local camera preview through `gesture/camera_preview.py`; frames are transient and are not saved.

The classifier checks finger joint angles and the position of fingertip landmarks relative to the wrist. For Thumbs Up, it additionally checks that the thumb tip is above the wrist in the image. These rules assume an approximately upright hand and can be affected by orientation, camera position, occlusion, and lighting. Unclear poses return no gesture instead of guessing. Handedness is accepted for a future orientation-aware improvement, but currently does not change classification.

This classifies pose shape only. It does not analyze movement behavior, verify a user's identity, prevent spoofing, or authenticate anyone. Classification quality has not been measured on a real camera dataset.

## Windows setup and testing

From the `SecureAir` directory in PowerShell:

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

Allow local camera access. Press **Q** or **Esc** to close the preview. If it cannot open the camera, close other apps using it or try `python -m gesture.camera_preview --camera 1`.

The secret remains in the local environment; never commit it. Camera frames are processed in memory and discarded. Obtain consent before using the camera around people.

## Stage status

Stages 2 and 3 provide local landmarks and static-pose labels only. Gesture sequences, enrollment, behavioral feature extraction, ML training, and authentication have not yet been implemented.
