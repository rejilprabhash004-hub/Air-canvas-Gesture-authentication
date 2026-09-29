# SecureAir

**Stage 5: consent-based local enrollment.** This is an educational research prototype, not a complete authentication system.

## Implemented components

- `gesture/hand_detector.py`: local MediaPipe Hands adapter; camera frames are transient and not saved.
- `gesture/landmarks.py`: validates and normalizes 21 XYZ landmarks.
- `gesture/gesture_recognition.py`: static-pose labels for Open Palm, Fist, Thumbs Up, Victory, and Pointing.
- `gesture/sequence.py`: ordered sequence tracker with neutral release and timeout behavior.
- `gesture/enrollment.py`: explicit-consent enrollment of 10–20 normalized 63-feature samples, with local profile deletion.
- Synthetic tests for validation and state behavior; no webcam is needed for unit tests.

Enrollment accepts normalized feature vectors only, not camera frames. It refuses missing consent, malformed or non-finite samples, invalid profile IDs, and overwriting an existing profile. Profiles are stored under the configured `data_dir` in `profiles/` as **unencrypted, sensitive biometric-derived JSON**. Use only on a device you control; protect the data directory and backups, do not sync it to shared/cloud storage, and use `delete_profile(data_dir, profile_id)` when deleting an enrollment. File deletion does not guarantee secure erasure from backups or storage media. This stage does not itself verify identity or authenticate.

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

Quit preview with **Q** or **Esc**. It is optional for tests. Obtain consent before camera use. Never commit the secret or local profiles.

See `docs/architecture.md`, `docs/development-plan.md`, and `docs/threat-model.md`. The original Flask project remains separate; its existing test runner deletes its database, so run that only against a disposable clone.
