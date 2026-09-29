# SecureAir

**Stage 8: in-memory user-bound gesture challenges.** This remains an educational research prototype, not an authentication system.

## Implemented components

- `gesture/hand_detector.py`: local MediaPipe Hands adapter; camera frames are transient and not saved.
- `gesture/landmarks.py`: validates and normalizes 21 XYZ landmarks.
- `gesture/gesture_recognition.py`: static-pose labels for Open Palm, Fist, Thumbs Up, Victory, and Pointing.
- `gesture/sequence.py`: ordered gesture tracking with release and timeout behavior.
- `gesture/enrollment.py`: explicit-consent local enrollment of 10–20 normalized feature vectors and profile deletion. Profiles are sensitive, unencrypted JSON; protect the data directory and backups.
- `gesture/behavioral_features.py`: timing-aware, palm-normalized motion summaries from timestamped landmarks.
- `gesture/model_evaluation.py`: Random Forest and RBF SVM comparison using session-disjoint holdout; real performance requires real labeled multi-session data.
- `backend/challenges.py`: unpredictable, profile-bound gesture sequences with expiry, one-time consumption, and in-memory lifecycle.

Challenge state is held only in this Python process; restarting it clears outstanding challenges. A wrong but valid response consumes the challenge, preventing retries. The challenge manager checks labels and profile binding, not camera/detector provenance, so it is not authentication or anti-spoofing by itself. Integrate only behind the later protected local service and validate input through the trusted capture path.

## Windows setup and checks

From this `SecureAir` directory in PowerShell:

```powershell
py -3.11 -m venv .venv
.\\.venv\\Scripts\\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
$env:SECUREAIR_SECRET_KEY = python -c "import secrets; print(secrets.token_hex(32))"
python -m pytest
ruff check .
python -m gesture.camera_preview
```

Quit preview with **Q** or **Esc**. Preview is optional for unit tests. Obtain consent before camera use; never commit secrets or local profiles. Profile files are plaintext and deletion cannot guarantee erasure from backups or storage media.

See `docs/architecture.md`, `docs/development-plan.md`, and `docs/threat-model.md`. The original Flask project remains separate; its existing test runner deletes its database, so run it only against a disposable clone.
