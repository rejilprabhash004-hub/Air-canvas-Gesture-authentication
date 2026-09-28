# SecureAir

**Stage 1: isolated project scaffold.** SecureAir is being developed alongside the original Flask project so existing behavior remains untouched.

## Goal and stage status

SecureAir is a local AI-assisted air-gesture authentication and security-monitoring research prototype. This stage lays out the package and documentation; it does not yet provide camera processing or authentication.

## Windows scaffold setup

1. Install Python 3.11 or newer.
2. Open PowerShell in `SecureAir` and run:

   ```powershell
   py -3.11 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install --upgrade pip
   pip install -r requirements-dev.txt
   python -m pytest
   ```

Camera library versions will need verification on the target Windows/Python version before the camera stages.

## Privacy and security principles

- Process camera frames locally; do not upload or retain raw footage.
- Store only necessary extracted features and offer profile deletion.
- Never collect website passwords or private page content.
- Monitor only explicitly configured domains.
- The planned service binds to loopback; it must not be exposed publicly.
- Hashing detects tampering; it is not encryption or proof against full host compromise.
- Educational prototype only; not a substitute for standard website authentication.

See `docs/architecture.md`, `docs/development-plan.md`, and `docs/threat-model.md`. The legacy test suite deletes its database; run it only in a disposable clone.
