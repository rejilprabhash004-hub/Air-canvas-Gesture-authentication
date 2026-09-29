# SecureAir

**Stage 9: transparent decision-policy primitive.** This remains an educational research prototype, not an authentication system.

## Implemented components

- `gesture/hand_detector.py`: local MediaPipe Hands adapter; camera frames are transient and not saved.
- `gesture/landmarks.py`: validates and normalizes 21 XYZ landmarks.
- `gesture/gesture_recognition.py`: static-pose labels for Open Palm, Fist, Thumbs Up, Victory, and Pointing.
- `gesture/sequence.py`: ordered gesture tracking with release and timeout behavior.
- `gesture/enrollment.py`: explicit-consent local enrollment of 10–20 normalized feature vectors and profile deletion. Profiles are sensitive, unencrypted JSON; protect the data directory and backups.
- `gesture/behavioral_features.py`: timing-aware, palm-normalized motion summaries from timestamped landmarks.
- `gesture/model_evaluation.py`: Random Forest and RBF SVM comparison using session-disjoint holdout; real performance requires real labeled multi-session data.
- `backend/challenges.py`: unpredictable, profile-bound gesture sequences with expiry, one-time consumption, and in-memory lifecycle.
- `backend/auth_decision.py`: fail-closed combination policy over sequence status, challenge outcome, and a caller-supplied behavioral match score with an explicit threshold.

The decision policy returns `ALLOW` only when all three required signals pass; otherwise it returns `DENY` with structured reasons. It validates the score and threshold as finite values in [0, 1]. The behavioral score is **caller supplied**: the existing Random Forest/SVM evaluator predicts gesture classes and does not provide calibrated user-identity confidence. No real labeled dataset is included, so no biometric performance or identity accuracy is claimed. Challenge state remains process-local. This is not yet an integrated or production authentication system; camera/detector provenance and real model training remain outside this policy.

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
