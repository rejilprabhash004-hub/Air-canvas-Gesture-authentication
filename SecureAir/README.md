# SecureAir

**Stage 6: normalized behavioral feature extraction.** This remains an educational research prototype, not an authentication system.

## Implemented components

- `gesture/hand_detector.py`: local MediaPipe Hands adapter; camera frames are transient and not saved.
- `gesture/landmarks.py`: validates and normalizes 21 XYZ landmarks.
- `gesture/gesture_recognition.py`: static-pose labels for Open Palm, Fist, Thumbs Up, Victory, and Pointing.
- `gesture/sequence.py`: ordered gesture tracking with release and timeout behavior.
- `gesture/enrollment.py`: explicit-consent local enrollment of 10–20 normalized feature vectors and profile deletion. Profiles are sensitive, unencrypted JSON; protect the data directory and backups.
- `gesture/behavioral_features.py`: timing-aware, palm-normalized motion summaries from ordered timestamped 21-point landmark sequences.

Behavioral feature extraction rejects malformed landmarks, non-finite or non-increasing timestamps, degenerate palm scales, and x/y coordinates outside the normalized image bounds [0, 1]. It reports duration, mean/peak speed, mean acceleration, path length, endpoint displacement, and path efficiency. Units are normalized palm lengths per second (or per second squared). It is a hand-crafted feature summary, not an ML model or an authentication result. Synthetic tests require no webcam.

## Windows setup and checks

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

Quit preview with **Q** or **Esc**. Preview is optional for unit tests. Obtain consent before camera use; never commit secrets or local profiles. Profile files are plaintext and deletion cannot guarantee erasure from backups or storage media.

See `docs/architecture.md`, `docs/development-plan.md`, and `docs/threat-model.md`. The original Flask project remains separate; its existing test runner deletes its database, so run it only against a disposable clone.
