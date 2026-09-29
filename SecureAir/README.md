# SecureAir

**Stage 10: loopback-only local API.** This remains an educational research prototype, not an authentication system.

## Implemented components

- `gesture/hand_detector.py`: local MediaPipe Hands adapter; camera frames are transient and not saved.
- `gesture/landmarks.py`: validates and normalizes 21 XYZ landmarks.
- `gesture/gesture_recognition.py`: static-pose labels for Open Palm, Fist, Thumbs Up, Victory, and Pointing.
- `gesture/sequence.py`: ordered gesture tracking with release and timeout behavior.
- `gesture/enrollment.py`: explicit-consent local enrollment of 10–20 normalized feature vectors and profile deletion. Profiles are sensitive, unencrypted JSON; protect the data directory and backups.
- `gesture/behavioral_features.py`: timing-aware, palm-normalized motion summaries.
- `gesture/model_evaluation.py`: Random Forest and RBF SVM comparison using session-disjoint holdout; real performance requires real labeled multi-session data.
- `backend/challenges.py`: unpredictable profile-bound gesture sequences with expiry and one-time consumption; state is in memory only.
- `backend/auth_decision.py`: fail-closed policy over gesture sequence, challenge outcome, and caller-supplied behavioral score.
- `backend/app.py`: FastAPI health and challenge routes with loopback-client checks and bearer-token protection for functional endpoints.

## Run the local API

From this `SecureAir` directory in PowerShell:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
$env:SECUREAIR_SECRET_KEY = python -c "import secrets; print(secrets.token_hex(32))"
python -m backend.app
```

The service defaults to `127.0.0.1:8000`; configuration refuses non-loopback bind addresses. `/health` is an unauthenticated local health response. Challenge creation and consumption require `Authorization: Bearer <SECUREAIR_SECRET_KEY>`. Treat this secret as sensitive and do not put it in source control, logs, or browser/page content. Challenges disappear when the process restarts.

`POST /challenges` accepts a profile ID and returns a random gesture sequence. `POST /challenges/{challenge_id}/consume` accepts the same profile ID, observed gesture labels, a sequence status, and a behavioral match score. The current API trusts those caller-supplied observations and score; it does not connect the webcam/detector, train/load an identity model, or authenticate a real user. A caller can forge these values, so this is a local integration prototype—not a protected production login. The present gesture-classification model does not produce calibrated identity confidence. Do not expose this service to a network or use it as a security boundary.

## Checks

```powershell
python -m pytest
ruff check .
```

These checks have not been run by the assistant in this environment. Preview with `python -m gesture.camera_preview` only after installing camera dependencies, and obtain consent before camera use. Never commit secrets or local profiles. Profile files are plaintext and deletion cannot guarantee erasure from backups or storage media. The original Flask project remains separate; its legacy test runner deletes its database, so run that only against a disposable clone.
