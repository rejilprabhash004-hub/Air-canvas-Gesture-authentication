"""Static accessibility regression checks for the extension UI."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "extension"


def test_popup_has_visible_keyboard_focus_and_forced_color_support():
    css = (EXTENSION / "popup.css").read_text(encoding="utf-8")
    markup = (EXTENSION / "popup.html").read_text(encoding="utf-8")
    assert re.search(r":focus-visible\s*\{[^}]*outline:\s*3px solid", css)
    assert "@media (forced-colors: active)" in css
    assert "outline-color: Highlight" in css
    assert 'id="manage" type="button"' in markup
    assert 'id="status" role="status"' in markup


def test_options_controls_are_labeled_and_have_large_focusable_targets():
    css = (EXTENSION / "options.css").read_text(encoding="utf-8")
    markup = (EXTENSION / "options.html").read_text(encoding="utf-8")
    assert re.search(r":focus-visible\s*\{[^}]*outline:\s*3px solid", css)
    assert "@media (forced-colors: active)" in css
    assert "outline-color: Highlight" in css
    assert re.search(r"input\s*\{[^}]*min-height:\s*44px", css)
    assert re.search(r"button\s*\{[^}]*min-height:\s*44px", css)
    assert '<label for="display-name">' in markup
    assert '<label for="domain">' in markup
    assert 'id="message" role="status" aria-live="polite"' in markup
    assert 'id="events-message" role="status" aria-live="polite"' in markup


def test_popup_controls_meet_target_size_and_status_is_announced():
    css = (EXTENSION / "popup.css").read_text(encoding="utf-8")
    assert re.search(r"button\s*\{[^}]*min-height:\s*44px", css)
    markup = (EXTENSION / "popup.html").read_text(encoding="utf-8")
    assert 'id="site" aria-live="polite"' in markup
    assert 'id="status" role="status"' in markup
