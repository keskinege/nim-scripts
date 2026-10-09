from __future__ import annotations

from typing import Any

from .config import Settings
from .errors import UsageError
from .http import request_json


def paged_get(
    settings: Settings,
    path: str,
    *,
    limit: int | None = None,
    offset: int | None = None,
    extra: dict[str, Any] | None = None,
):
    params: dict[str, Any] = dict(extra or {})
    if limit is not None:
        if not isinstance(limit, int) or not 0 <= limit <= 100:
            raise UsageError("--limit must be 0..100")
        params["limit"] = limit
    if offset is not None:
        if not isinstance(offset, int) or offset < 0:
            raise UsageError("--offset must be >= 0")
        params["offset"] = offset
    return request_json(settings, "GET", path, params=params or None)
