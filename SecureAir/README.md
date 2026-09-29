# SecureAir

**Stage 7: model-evaluation pipeline.** This remains an educational research prototype, not an authentication system.

## Implemented components

- `gesture/hand_detector.py`: local MediaPipe Hands adapter; camera frames are transient and not saved.
- `gesture/landmarks.py`: validates and normalizes 21 XYZ landmarks.
- `gesture/gesture_recognition.py`: static-pose labels for Open Palm, Fist, Thumbs Up, Victory, and Pointing.
- `gesture/sequence.py`: ordered gesture tracking with release and timeout behavior.
- `gesture/enrollment.py`: explicit-consent local enrollment of 10–20 normalized feature vectors and profile deletion. Profiles are sensitive, unencrypted JSON; protect the data directory and backups.
- `gesture/behavioral_features.py`: timing-aware, palm-normalized motion summaries from timestamped landmarks.
- `gesture/model_evaluation.py`: compares Random Forest and RBF SVM with a session-disjoint holdout split and reports accuracy, macro precision/recall/F1, and confusion matrices.

The model evaluator requires real labeled feature rows and a session ID for each row. All rows from one session remain together in either training or test data. Each class must occur in both partitions. The repository currently contains no real labeled dataset, so **no measured performance is reported**. Synthetic test data only checks pipeline behavior; it is not evidence of recognition accuracy. Results depend on dataset quality and may not generalize to new people, cameras, or sessions. This code does not yet persist trained models or authenticate users.

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
