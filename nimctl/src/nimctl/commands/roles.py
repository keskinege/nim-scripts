from __future__ import annotations

import typer

from .. import http
from ..config import resolve_settings
from ..render import render

app = typer.Typer(no_args_is_help=True, help="Manage roles and module features.")


@app.command("list")
def list_(show_details: bool = typer.Option(False, "--show-details")) -> None:
    settings = resolve_settings()
    params = {"showDetails": "true"} if show_details else None
    render(http.request_json(settings, "GET", "/roles", params=params), mode=settings.output)


@app.command("get")
def get(name: str) -> None:
    settings = resolve_settings()
    render(http.request_json(settings, "GET", f"/roles/{name}"), mode=settings.output)


@app.command("features")
def features() -> None:
    settings = resolve_settings()
    render(http.request_json(settings, "GET", "/features"), mode=settings.output)
