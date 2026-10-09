from __future__ import annotations

import json
import sys
from collections.abc import Iterable
from typing import Any, TextIO

from .errors import UsageError


def _rows(obj: Any) -> Iterable[Any]:
    if isinstance(obj, dict) and "items" in obj and isinstance(obj["items"], list):
        return obj["items"]
    if isinstance(obj, list):
        return obj
    return [obj]


def _get(obj: Any, dotted: str) -> Any:
    for part in dotted.split("."):
        if isinstance(obj, dict):
            obj = obj.get(part)
        else:
            return None
    return obj


def render(
    obj: Any, *, mode: str = "json", columns: list[str] | None = None, out: TextIO | None = None
) -> None:
    out = out or sys.stdout
    if mode == "json":
        out.write(json.dumps(obj, indent=2) + "\n")
    elif mode == "raw":
        out.write((obj if isinstance(obj, str) else json.dumps(obj)) + "\n")
    elif mode == "table":
        if not columns:
            raise UsageError("table output requires column definitions")
        for row in _rows(obj):
            out.write("\t".join(str(_get(row, col)) for col in columns) + "\n")
    else:
        raise UsageError(f"unknown output mode: {mode}")
