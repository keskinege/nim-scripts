from __future__ import annotations

import time

import pytest

from nimctl import spec
from nimctl.config import GlobalOptions, resolve_settings, set_globals
from nimctl.errors import HttpError

DOC = {
    "openapi": "3.0.3",
    "paths": {
        "/systems": {"get": {"tags": ["systems"]}},
        "/systems/x": {"get": {"tags": ["systems"]}, "delete": {"tags": ["systems"]}},
        "/health": {"get": {"tags": ["Health"]}},
    },
}


def test_cache_path_is_host_keyed(env, monkeypatch):
    monkeypatch.setenv("NIMCTL_HOST", "https://a.test")
    a = spec.spec_cache_path(resolve_settings())
    monkeypatch.setenv("NIMCTL_HOST", "https://b.test")
    b = spec.spec_cache_path(resolve_settings())
    assert a != b


def test_fetch_spec_downloads_then_uses_cache(env, patched_client):
    fake = patched_client()
    # Only one queued response: a second network hit would raise from the fake.
    fake.add("GET", "/ui/manager.json", DOC)
    assert spec.fetch_spec(resolve_settings())["openapi"] == "3.0.3"
    assert spec.fetch_spec(resolve_settings())["openapi"] == "3.0.3"
    assert len([c for c in fake.calls if c.url.path == "/ui/manager.json"]) == 1


def test_stale_cache_triggers_request(env, patched_client, monkeypatch):
    monkeypatch.setenv("NIMCTL_SPEC_TTL", "0")
    fake = patched_client()
    fake.add("GET", "/ui/manager.json", DOC)
    spec.fetch_spec(resolve_settings())
    fake.add("GET", "/ui/manager.json", DOC)
    spec.fetch_spec(resolve_settings())
    assert len([c for c in fake.calls if c.url.path == "/ui/manager.json"]) == 2


def test_refresh_flag_forces_request(env, patched_client):
    fake = patched_client()
    fake.add("GET", "/ui/manager.json", DOC)
    spec.fetch_spec(resolve_settings())
    set_globals(GlobalOptions(refresh=True))
    fake.add("GET", "/ui/manager.json", DOC)
    spec.fetch_spec(resolve_settings())
    assert len([c for c in fake.calls if c.url.path == "/ui/manager.json"]) == 2


def test_failed_refresh_preserves_cache(env, patched_client):
    fake = patched_client()
    fake.add("GET", "/ui/manager.json", DOC)
    spec.fetch_spec(resolve_settings())
    cache = spec.spec_cache_path(resolve_settings())
    before = cache.read_text()
    set_globals(GlobalOptions(refresh=True))
    fake.add("GET", "/ui/manager.json", {"message": "boom"}, status=500)
    with pytest.raises(HttpError):
        spec.fetch_spec(resolve_settings())
    assert cache.read_text() == before


def test_is_fresh_false_for_missing_file(env):
    assert spec.is_fresh(spec.spec_cache_path(resolve_settings()), 3600) is False


def test_is_fresh_age(env, monkeypatch):
    import os

    path = spec.spec_cache_path(resolve_settings())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{}")
    assert spec.is_fresh(path, 3600) is True
    old = time.time() - 10
    os.utime(path, (old, old))
    assert spec.is_fresh(path, 1) is False


def test_api_tags_sorted_unique():
    assert spec.api_tags(DOC) == ["Health", "systems"]


def test_api_paths_filters_and_uppercases():
    assert spec.api_paths(DOC, "systems") == [
        ("DELETE", "/systems/x"),
        ("GET", "/systems"),
        ("GET", "/systems/x"),
    ]


def test_api_paths_unknown_tag_is_empty():
    assert spec.api_paths(DOC, "nope") == []
