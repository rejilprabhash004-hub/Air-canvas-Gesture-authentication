"""Static privacy-contract checks for the Manifest V3 extension."""
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "extension"


def test_extension_keeps_minimal_permissions_and_no_host_access():
    manifest = json.loads((EXTENSION / "manifest.json").read_text(encoding="utf-8"))
    assert set(manifest["permissions"]) == {"activeTab", "storage"}
    assert "host_permissions" not in manifest
    assert "content_scripts" not in manifest


def test_no_background_tab_or_navigation_monitoring():
    worker = (EXTENSION / "service-worker.js").read_text(encoding="utf-8")
    assert "tabs.onUpdated" not in worker
    assert "webNavigation" not in worker
    assert "history" not in worker
    assert "fetch(" not in worker


def test_explicit_check_event_records_only_exact_host_metadata():
    popup = (EXTENSION / "popup.js").read_text(encoding="utf-8")
    assert "chrome.storage.local.set({ activityEvents: nextEvents })" in popup
    assert 'entry?.enabled === true' in popup
    assert 'status: "enabled_status_checked"' in popup
    assert "url.pathname" not in popup
    assert "url.search" not in popup
    assert "document.body" not in popup
    assert "fetch(" not in popup
    assert re.search(r"\.slice\(-200\)", popup)


def test_options_history_uses_text_nodes_and_can_clear_local_events():
    options = (EXTENSION / "options.js").read_text(encoding="utf-8")
    markup = (EXTENSION / "options.html").read_text(encoding="utf-8")
    assert 'item.textContent = `${timestamp} — ${event.hostname} — status checked`' in options
    assert "innerHTML" not in options
    assert 'id="clear-events"' in markup
    assert 'chrome.storage.local.set({ activityEvents: [] })' in options
