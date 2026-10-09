from __future__ import annotations

import typer

from .. import http
from ..config import resolve_settings
from ..render import render

app = typer.Typer(no_args_is_help=True, help="List NGINX staged configurations.")


@app.command("list")
def list_() -> None:
    settings = resolve_settings()
    render(http.request_json(settings, "GET", "/configs"), mode=settings.output)


@app.command("get")
def get(config_uid: str) -> None:
    settings = resolve_settings()
    render(http.request_json(settings, "GET", f"/configs/{config_uid}"), mode=settings.output)
