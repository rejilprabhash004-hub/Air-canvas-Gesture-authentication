"""Validated configuration and private local paths for the SecureAir prototype.

Configuration errors fail early: never silently bind the local service to a public
interface, and never use a known development secret. This module does not capture
or persist biometric data.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path


class ConfigurationError(ValueError):
    """Raised when configuration would violate a SecureAir safety invariant."""


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    host: str
    port: int
    secret_key: str
    lockout_max_attempts: int
    lockout_seconds: int
    challenge_seconds: int


def load_settings(environ: dict[str, str] | None = None,
                  project_root: Path | None = None) -> Settings:
    """Load validated values from environment; injectable inputs simplify tests."""
    env = os.environ if environ is None else environ
    root = Path(project_root) if project_root is not None else Path(__file__).resolve().parents[1]
    data_dir = Path(env.get("SECUREAIR_DATA_DIR", str(root / "data")).strip()).expanduser()
    host = env.get("SECUREAIR_HOST", "127.0.0.1").strip()
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise ConfigurationError("SecureAir service must bind to a loopback address.")

    try:
        port = int(env.get("SECUREAIR_PORT", "8000"))
        attempts = int(env.get("SECUREAIR_LOCKOUT_MAX_ATTEMPTS", "3"))
        lockout = int(env.get("SECUREAIR_LOCKOUT_SECONDS", "300"))
        challenge = int(env.get("SECUREAIR_CHALLENGE_SECONDS", "60"))
    except ValueError as exc:
        raise ConfigurationError("Port and timeout settings must be integers.") from exc
    if not 1 <= port <= 65535:
        raise ConfigurationError("Port must be between 1 and 65535.")
    if not 1 <= attempts <= 20 or not 30 <= lockout <= 86400:
        raise ConfigurationError("Lockout configuration is outside the safe range.")
    if not 5 <= challenge <= 300:
        raise ConfigurationError("Challenge lifetime must be between 5 and 300 seconds.")

    secret = env.get("SECUREAIR_SECRET_KEY", "")
    if len(secret) < 32 or re.fullmatch(r"(?i)(change.?me|dev.?key|secret|password).*", secret):
        raise ConfigurationError(
            "Set SECUREAIR_SECRET_KEY to a unique random secret of at least 32 characters."
        )
    return Settings(data_dir, host, port, secret, attempts, lockout, challenge)
