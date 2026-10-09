from __future__ import annotations

import typer

from .. import http
from ..config import resolve_settings
from ..pagination import paged_get
from ..render import render

app = typer.Typer(no_args_is_help=True, help="Manage certificates.")


@app.command("list")
def list_(
    limit: int | None = typer.Option(None, "--limit", min=0, max=100),
    offset: int | None = typer.Option(None, "--offset", min=0),
) -> None:
    settings = resolve_settings()
    render(paged_get(settings, "/certs", limit=limit, offset=offset), mode=settings.output)


@app.command("get")
def get(cert_name: str) -> None:
    settings = resolve_settings()
    render(http.request_json(settings, "GET", f"/certs/{cert_name}"), mode=settings.output)


@app.command("summary")
def summary() -> None:
    settings = resolve_settings()
    render(http.request_json(settings, "GET", "/certs/summary"), mode=settings.output)


@app.command("delete")
def delete(cert_name: str) -> None:
    settings = resolve_settings()
    http.request(settings, "DELETE", f"/certs/{cert_name}")
