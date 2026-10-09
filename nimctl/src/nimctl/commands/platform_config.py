from __future__ import annotations

import typer

from .. import http
from ..config import resolve_settings
from ..render import render

app = typer.Typer(no_args_is_help=True, help="Query the platform configuration and inventory.")


@app.command("show")
def show(config_name: str) -> None:
    settings = resolve_settings()
    render(
        http.request_json(settings, "GET", f"/platform-config/{config_name}"),
        mode=settings.output,
    )


@app.command("inventory")
def inventory() -> None:
    settings = resolve_settings()
    render(http.request_json(settings, "GET", "/inventory"), mode=settings.output)
