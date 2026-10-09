from __future__ import annotations

import typer

from .. import http
from ..config import resolve_settings
from ..errors import HttpError
from ..render import render


def health() -> None:
    settings = resolve_settings()
    render(http.request_json(settings, "GET", "/health"), mode=settings.output)


def modules(licensed: bool = typer.Option(False, "--licensed")) -> None:
    settings = resolve_settings()
    path = "/modules/licensed" if licensed else "/modules"
    render(http.request_json(settings, "GET", path), mode=settings.output)


def license_cmd(status: bool = typer.Option(False, "--status")) -> None:
    settings = resolve_settings()
    path = "/license/status" if status else "/license"
    render(http.request_json(settings, "GET", path), mode=settings.output)


def version() -> None:
    settings = resolve_settings()
    try:
        data = http.request_json(settings, "GET", "/versions")
    except HttpError:
        data = None
    if data is None:
        typer.echo(f"api_version={settings.api_version}")
    else:
        render(data, mode=settings.output)
