# SecureAir Windows setup and viva guide

## 1. Scope and safety

SecureAir is an educational local research prototype. It is **not production authentication** and must not protect real accounts or resources. The submitted gesture sequence and behavioral score are caller-supplied and forgeable; the model has no validated identity-confidence dataset. Challenges and portal sessions are process-local. Local enrollment features, backend events, extension history, reports, and digests are not encrypted. The event hash chain has no external trust anchor. The extension shows an explicit local status only; it does not authenticate or block navigation.

Camera frames are processed locally by the preview and are not intentionally persisted. Run only on data you are authorized to process. Never commit `.env` secrets, profiles, databases, report files, or digest files.

## 2. Requirements

- Windows 10/11 with Python 3.11 available as `py -3.11`.
- Git and a terminal such as PowerShell.
- A webcam only for the optional local hand preview; synthetic tests do not need one.
- Microsoft Visual C++ runtime or other platform requirements may affect OpenCV/MediaPipe installation. Follow trusted upstream package guidance if installation fails; do not disable security controls to bypass errors.

## 3. Get the branch and create an environment

Clone the repository if needed, then check out the SecureAir development branch:

```powershell
git clone https://github.com/rejilprabhash004-hub/Air-canvas-Gesture-authentication.git
cd Air-canvas-Gesture-authentication
git switch feature/secureair-stage-01
cd SecureAir
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
```

If PowerShell blocks activation under your organization's policy, do not weaken system execution policy. Use the venv interpreter explicitly instead: `.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt`, and substitute `.\.venv\Scripts\python.exe` for `python` in later commands.

## 4. Configure a fresh local API secret

The API requires a unique random secret of at least 32 characters. In PowerShell, generate one and set it in the current shell:

```powershell
$env:SECUREAIR_SECRET_KEY = python -c "import secrets; print(secrets.token_hex(32))"
```

Keep this shell open for the API. The secret is process environment configuration; do not paste it into source code, browser extension settings, screenshots, or Git. If you open a new shell for the portal, set the **same** secret there using a secure local method. Avoid saving it in shell history or project files. Optional service settings include `SECUREAIR_HOST` (loopback only), `SECUREAIR_PORT` (default 8000), and `SECUREAIR_DATA_DIR` (local data directory); defaults are safer for a first run.

## 5. Run tests and lint

From the `SecureAir` directory:

```powershell
python -m pytest
ruff check .
```

A passing test suite checks implemented behavior only; it does not validate recognition accuracy, identity assurance, accessibility compliance, or production security. Record actual command output and environment details when presenting results. Do not claim tests passed unless you ran them on the current commit.

## 6. Optional local camera preview

With dependencies installed and camera permission granted:

```powershell
python -m gesture.camera_preview --camera 0
```

Use `--camera 1` if the desired camera has a different device index. Press **Q** or **Esc** to close. The preview is a diagnostic only. It annotates the displayed frames in memory and does not save a video. If the camera cannot open, close other camera applications, check Windows privacy settings, and retry; synthetic landmark tests remain camera-independent.

## 7. Run the loopback API and portal

Keep API and portal in separate PowerShell windows. In the first window, from `SecureAir`, activate the environment, set the secret, and start the service:

```powershell
.\.venv\Scripts\Activate.ps1
$env:SECUREAIR_SECRET_KEY = python -c "import secrets; print(secrets.token_hex(32))"
python -m backend.app
```

For the second window, copy the generated secret securely from the first process environment using your local secret-management practice; do not generate a different secret. Then:

```powershell
cd <path-to-repository>\SecureAir
.\.venv\Scripts\Activate.ps1
$env:SECUREAIR_SECRET_KEY = "<same-secret-from-first-window>"
python -m uvicorn demo_portal.app:app --host 127.0.0.1 --port 8765
```

Open `http://127.0.0.1:8765/`. The portal requests a server-side challenge from the loopback API; enter a gesture sequence and submit the demo form. Inputs remain forgeable, so this demonstrates control flow only. Stop each process with **Ctrl+C**.

For a reliable classroom demo, run tests first, verify both processes bind only to loopback, and have a no-camera explanation ready. Do not expose either service on a LAN or public interface.

## 8. Load the browser extension (optional)

In Chromium-based browser extension management, enable developer mode and load the unpacked folder `SecureAir/extension`. Open its toolbar popup on a normal HTTP(S) page, then use **Manage sites** to configure an exact hostname and inspect/clear local explicit-check history. The extension's permissions are `activeTab` and `storage`; it has no host permissions or background navigation collection. Its status is a preference display, not access control.

## 9. Architecture talking points

- `gesture/`: local hand detection, normalized landmarks, geometric labels, sequence state machine, and optional camera preview.
- `backend/config.py`: strict loopback configuration and secret validation.
- `backend/challenges.py` and `backend/auth_decision.py`: expiring one-time challenges and fail-closed decision policy.
- `backend/app.py`: bearer-protected loopback API; observations and behavioral scores are explicitly caller-supplied.
- `backend/database.py`, `security_events.py`, `security_event_hashes.py`, `security_event_chain.py`: isolated SQLite schema, minimized allowlisted events, canonical hashes, chain verification, and guarded profile deletion.
- `backend/activity_dashboard.py`: token-gated, read-only paginated event queries; verifies chain integrity and omits details/hashes.
- `backend/event_reports.py` and `report_integrity.py`: local minimized PDF/CSV/JSON output and exact-byte digest verification.
- `extension/`: explicit-host local status popup/options; no background monitoring or remote calls.
- `demo_portal/`: loopback integration demonstration; process-local sessions and forgeable visitor inputs.

## 10. Viva questions with concise answers

| Question | Suggested answer |
|---|---|
| What does the prototype demonstrate? | Local hand-landmark processing, geometric gesture labels, one-time challenge flow, an isolated event store, and a loopback portal integration. |
| Is this a biometric authentication product? | No. There is no validated labeled identity dataset or calibrated identity-confidence model, and request signals are forgeable. |
| Why use a challenge? | A short-lived, user-bound, single-use challenge limits simple replay of an earlier sequence; it does not prove the signal came from a camera. |
| Why does the API bind to loopback? | It reduces network exposure for a local prototype. It does not protect against malware or users/processes on the same machine. |
| What does the event hash chain do? | It detects inconsistent changes when verified. A person able to rewrite the database can recompute the chain; there is no external anchor. |
| Why minimize log fields? | To avoid storing credentials, raw frames, landmarks, arbitrary request content, and unnecessary event details in query/export paths. |
| What does the extension protect? | Nothing by itself. It displays status for an explicitly configured hostname after a user opens the popup; it does not block access or replace site authentication. |
| How are reports checked? | SHA-256 compares exact bytes to a separately held digest. It proves neither authorship nor trustworthiness if the digest can also be replaced. |
| What evidence supports a performance claim? | A labeled, consented dataset with user/session-disjoint evaluation, documented metrics, representative devices/conditions, and uncertainty analysis. This repository alone does not establish accuracy. |
| What would be needed before deployment? | Independent security and privacy review, trusted camera/signal provenance, validated models, durable challenge/session handling, external integrity checkpoints, accessibility assessment, monitoring, recovery design, and threat-model acceptance. |

## 11. Troubleshooting and honest reporting

- **Missing `py` or Python 3.11:** install Python 3.11 from an approved source and ensure the launcher is available, or use a compatible `python` executable explicitly.
- **Dependency install failure:** note the exact package, Python version, and error; verify architecture and upstream wheel support. Do not silently substitute dependency versions in a reproducible demo.
- **API returns not configured:** set the same fresh `SECUREAIR_SECRET_KEY` in the API process before launch.
- **Portal reports service unavailable:** verify API is running on `127.0.0.1:8000`, portal uses the same secret, and no redirect/proxy or other process is intercepting loopback.
- **API authentication fails:** restart both processes with the same secret; do not put the bearer key in browser JavaScript.
- **Camera permission/open failure:** verify Windows camera privacy permission, camera index, and that another app is not holding the device.
- **Tests fail:** preserve the failing output and investigate before presenting a passing result. The legacy project test suite may have different dependencies; this guide's commands run inside `SecureAir`.

Manual assistive-technology, browser rendering, camera, and dynamic security checks have not been performed by this guide. Present them as remaining validation, not completed evidence.
