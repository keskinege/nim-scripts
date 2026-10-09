from __future__ import annotations

import typer

from .. import http
from ..config import resolve_settings
from ..render import render

app = typer.Typer(no_args_is_help=True, help="Query metrics, dimension and event catalogs.")

_KINDS = {"metrics", "dimensions", "events"}


@app.command("show")
def show(kind: str, name: str | None = None) -> None:
    if kind not in _KINDS:
        raise typer.BadParameter(f"kind must be one of {', '.join(sorted(_KINDS))}")
    settings = resolve_settings()
    path = f"/analytics/catalogs/{kind}"
    if name:
        path = f"{path}/{name}"
    render(http.request_json(settings, "GET", path), mode=settings.output)
