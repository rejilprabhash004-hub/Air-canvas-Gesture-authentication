"""Configuration validation tests; no camera/service is started."""
import pytest

from backend.config import ConfigurationError, load_settings


GOOD = {"SECUREAIR_SECRET_KEY": "x" * 48}


def test_defaults_are_loopback_only(tmp_path):
    settings = load_settings(GOOD, tmp_path)
    assert settings.host == "127.0.0.1"
    assert settings.port == 8000
    assert settings.data_dir == tmp_path / "data"
    assert settings.challenge_seconds == 60


def test_rejects_public_bind(tmp_path):
    with pytest.raises(ConfigurationError, match="loopback"):
        load_settings({**GOOD, "SECUREAIR_HOST": "0.0.0.0"}, tmp_path)


@pytest.mark.parametrize("secret", ["", "dev-key-please-change", "short"])
def test_rejects_missing_or_weak_secret(tmp_path, secret):
    with pytest.raises(ConfigurationError, match="SECRET_KEY"):
        load_settings({"SECUREAIR_SECRET_KEY": secret}, tmp_path)


def test_rejects_out_of_range_challenge(tmp_path):
    with pytest.raises(ConfigurationError, match="Challenge lifetime"):
        load_settings({**GOOD, "SECUREAIR_CHALLENGE_SECONDS": "999"}, tmp_path)
