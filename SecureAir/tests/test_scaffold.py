"""Stage-1 tests guard package import and safe defaults without touching legacy app."""
from pathlib import Path

from backend.config import load_settings


def test_secureair_scaffold_isolated_from_legacy_project():
    root = Path(__file__).resolve().parents[1]
    assert root.name == "SecureAir"
    assert (root / "backend" / "config.py").is_file()
    assert (root.parent / "app.py").is_file()


def test_config_does_not_create_runtime_data_during_load(tmp_path):
    settings = load_settings({"SECUREAIR_SECRET_KEY": "a" * 48}, tmp_path)
    assert settings.data_dir == tmp_path / "data"
    assert not settings.data_dir.exists()
