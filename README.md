# Air-Gesture Based Cybersecurity Dashboard

MSc Cybersecurity / Digital Forensics project. A touchless cybersecurity
dashboard combining hand-gesture recognition, gesture-based two-factor
authentication, brute-force protection, simulated security-event
monitoring, forensic/audit logging, and gesture-controlled navigation.

Full academic write-up: `docs/project-report.docx`.
Test plan and results: `tests/test_plan.md`.

## Tech stack

Python 3.10/3.11 · Flask · OpenCV · MediaPipe (pinned `0.10.14`) · SQLite ·
Chart.js · Werkzeug (password hashing)

## Setup (Windows)

```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python -c "import secrets; print(secrets.token_hex(32))"
```
Paste the generated key into `.env` as `FLASK_SECRET_KEY`.

```
python database\database.py
python app.py
```

Visit `http://127.0.0.1:5000`. A seeded admin account is created on
first run — **username `admin`, password `ChangeMe123!`, gesture
sequence INDEX → TWO_FINGERS → OPEN_PALM → THUMB_UP** — printed to the
console on first run. Change the password before any real demo.

## Verify your camera/gesture setup before demoing

```
python computer_vision\test_webcam.py
```
Confirms all 5 gestures (INDEX, TWO_FINGERS, OPEN_PALM, THUMB_UP, FIST)
classify correctly for your hand/lighting/camera before you rely on it
during login.

## Running tests

```
python tests\test_suite.py
```
Runs all 12 required test cases (see `tests/test_plan.md` for the
documented expected-vs-actual results). Stop `app.py` first — the test
suite resets the database file.

## Project structure

```
gesture-cyberdash/
├── app.py                     Main Flask application, all routes
├── config.py                  Environment-driven configuration
├── requirements.txt
├── .env.example
├── database/                  schema.sql + connection/init helpers
├── authentication/            Password auth + gesture-sequence auth
├── computer_vision/           MediaPipe hand detection + gesture classifier
├── security/                  Brute-force, audit logging, event generation
├── dashboard/                 Chart.js data aggregation + gesture navigation
├── templates/, static/        Flask views + CSS
├── tests/                     Automated suite + documented test plan
└── docs/                      Full academic report (docx)
```

## Configuration (`.env`)

| Variable | Purpose | Default |
|---|---|---|
| `FLASK_SECRET_KEY` | Session signing key — **must** be a real random value | none, warns if unset |
| `LOCKOUT_MAX_ATTEMPTS` | Failed attempts before account lock | 3 |
| `LOCKOUT_DURATION_MINUTES` | How long a lockout lasts | 5 |
| `SESSION_TIMEOUT_MINUTES` | Idle timeout before forced re-login | 15 |
| `MP_DETECTION_CONFIDENCE` / `MP_TRACKING_CONFIDENCE` | MediaPipe thresholds — lower if gestures feel unresponsive | 0.7 |
| `FLASK_DEBUG` | Dev auto-reload — **never true beyond local dev** | false |
| `SESSION_COOKIE_SECURE` | HTTPS-only cookies — **true required off localhost** | false |

## Known limitations (see full report for details)

- Single shared webcam / single active gesture session — not designed
  for concurrent multi-user gesture auth on one machine.
- Repeating the *same* gesture twice in a row (mid-sequence or in
  navigation) requires visibly dropping your hand between reps.
- No CSRF-safe multi-tab session handling beyond Flask's default
  cookie-session model.

## Troubleshooting quick index

| Symptom | Likely cause |
|---|---|
| `mediapipe has no attribute 'solutions'` | Unpinned mediapipe — reinstall from `requirements.txt` exactly |
| Webcam won't open | Another app (Teams/Zoom/browser) holding the camera |
| Stuck on gesture-auth `DENIED` | Check `computer_vision/test_webcam.py` first to isolate camera vs. logic issues |
| `400 Invalid CSRF token` | Session cookie blocked/cleared mid-form; reload the page |
| Locked out during your own testing | Wait out `LOCKOUT_DURATION_MINUTES`, or delete `database/cyberdash.db` and re-seed |
