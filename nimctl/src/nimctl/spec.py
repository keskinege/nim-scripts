from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

from .config import Settings
from .http import request_bytes_to

_METHODS = {"get", "post", "put", "patch", "delete"}


def cache_dir() -> Path:
    return Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "nimctl"


def spec_cache_path(settings: Settings) -> Path:
    key = hashlib.sha256(f"{settings.host}|{settings.api_version}".encode()).hexdigest()[:16]
    return cache_dir() / f"spec-{key}.json"


def is_fresh(path: Path, ttl: int) -> bool:
    try:
        return (time.time() - path.stat().st_mtime) < ttl
    except FileNotFoundError:
        return False


def fetch_spec(settings: Settings, *, refresh: bool | None = None) -> dict[str, Any]:
    path = spec_cache_path(settings)
    force = settings.refresh if refresh is None else refresh
    if not force and path.exists() and is_fresh(path, settings.spec_ttl):
        return json.loads(path.read_text())
    request_bytes_to(settings, "/ui/manager.json", path)
    return json.loads(path.read_text())


def api_tags(document: dict[str, Any]) -> list[str]:
    tags: set[str] = set()
    for operations in document.get("paths", {}).values():
        for method, operation in operations.items():
            if method in _METHODS:
                tags.update(operation.get("tags", []))
    return sorted(tags)


def api_paths(document: dict[str, Any], tag: str) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for path, operations in document.get("paths", {}).items():
        for method, operation in operations.items():
            if method in _METHODS and tag in operation.get("tags", []):
                found.append((method.upper(), path))
    return sorted(found)
