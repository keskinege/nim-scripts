from __future__ import annotations

import typer

from .. import http
from ..config import resolve_settings
from ..pagination import paged_get
from ..render import render

app = typer.Typer(no_args_is_help=True, help="Manage NGINX instances.")


@app.command("list")
def list_(
    limit: int | None = typer.Option(None, "--limit", min=0, max=100),
    offset: int | None = typer.Option(None, "--offset", min=0),
) -> None:
    settings = resolve_settings()
    data = paged_get(settings, "/instances", limit=limit, offset=offset)
    render(data, mode=settings.output, columns=["displayName", "uid", "systemUid"])


@app.command("get")
def get(system_uid: str, nginx_uid: str) -> None:
    settings = resolve_settings()
    render(
        http.request_json(settings, "GET", f"/systems/{system_uid}/instances/{nginx_uid}"),
        mode=settings.output,
        columns=["displayName", "uid", "systemUid"],
    )


@app.command("list-by-system")
def list_by_system(
    system_uid: str,
    limit: int | None = typer.Option(None, "--limit", min=0, max=100),
) -> None:
    settings = resolve_settings()
    data = paged_get(settings, f"/systems/{system_uid}/instances", limit=limit)
    render(data, mode=settings.output, columns=["displayName", "uid"])


@app.command("delete")
def delete(system_uid: str, nginx_uid: str) -> None:
    settings = resolve_settings()
    http.request(settings, "DELETE", f"/systems/{system_uid}/instances/{nginx_uid}")
