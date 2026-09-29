"""Tests for explicit protected-site CRUD, normalization, and exact matching."""
import pytest

from backend.database import DATABASE_FILENAME, initialize_database
from backend.protected_sites import ProtectedSiteError, ProtectedSiteStore, normalize_domain


def make_store(tmp_path):
    path = initialize_database(tmp_path / DATABASE_FILENAME)
    return ProtectedSiteStore(path)


def test_add_normalizes_and_lists_configured_hostnames(tmp_path):
    store = make_store(tmp_path)
    site = store.add("  EXAMPLE.COM. ", timestamp="2026-09-29T00:00:00+00:00")
    assert site.domain == "example.com"
    assert site.enabled is True
    assert [item.domain for item in store.list()] == ["example.com"]
    assert store.is_enabled("Example.com") is True


def test_duplicate_add_is_rejected_after_canonicalization(tmp_path):
    store = make_store(tmp_path)
    store.add("Example.com", timestamp="t1")
    with pytest.raises(ProtectedSiteError, match="already configured"):
        store.add("example.com.", timestamp="t2")


def test_disable_enable_and_remove_only_affect_explicit_hostname(tmp_path):
    store = make_store(tmp_path)
    store.add("example.com", timestamp="t1")
    updated = store.set_enabled("example.com", False, timestamp="t2")
    assert updated.enabled is False
    assert updated.created_at == "t1"
    assert updated.updated_at == "t2"
    assert store.is_enabled("example.com") is False
    assert store.list(enabled_only=True) == []

    updated = store.set_enabled("example.com", True, timestamp="t3")
    assert updated.enabled is True
    assert store.is_enabled("example.com") is True
    assert store.remove("EXAMPLE.COM") is True
    assert store.remove("example.com") is False
    assert store.is_enabled("example.com") is False


def test_subdomain_does_not_inherit_parent_protection(tmp_path):
    store = make_store(tmp_path)
    store.add("example.com", timestamp="t1")
    assert store.is_enabled("example.com") is True
    assert store.is_enabled("shop.example.com") is False


@pytest.mark.parametrize("domain", [
    "", "localhost", "example", "https://example.com", "example.com/path",
    "user@example.com", "example.com:443", "127.0.0.1", "[::1]", "-bad.example",
    "bad-.example", "bad..example", "bad_domain.example", "example.c",
])
def test_rejects_non_fqdn_or_non_hostname_input(domain):
    with pytest.raises(ProtectedSiteError):
        normalize_domain(domain)


def test_normalizes_unicode_domain_to_idna_ascii():
    assert normalize_domain("bücher.de") == "xn--bcher-kva.de"


def test_setting_operations_reject_invalid_types_and_unknown_hosts(tmp_path):
    store = make_store(tmp_path)
    with pytest.raises(ProtectedSiteError):
        store.list(enabled_only=1)
    with pytest.raises(ProtectedSiteError, match="boolean"):
        store.set_enabled("example.com", 1, timestamp="t1")
    with pytest.raises(ProtectedSiteError, match="not configured"):
        store.set_enabled("example.com", True, timestamp="t1")
    with pytest.raises(ProtectedSiteError, match="timestamp"):
        store.add("example.com", timestamp=" ")
