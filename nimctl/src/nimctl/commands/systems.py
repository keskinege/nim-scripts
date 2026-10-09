from __future__ import annotations

import json
from pathlib import Path

import typer

from .. import http
from ..config import resolve_settings
from ..pagination import paged_get
from ..render import render

app = typer.Typer(no_args_is_help=True, help="Manage systems.")


@app.command("list")
def list_(
    limit: int | None = typer.Option(None, "--limit", min=0, max=100),
    offset: int | None = typer.Option(None, "--offset", min=0),
) -> None:
    settings = resolve_settings()
    data = paged_get(settings, "/systems", limit=limit, offset=offset)
    render(data, mode=settings.output, columns=["hostname", "uid"])


@app.command("get")
def get(system_uid: str) -> None:
    settings = resolve_settings()
    render(
        http.request_json(settings, "GET", f"/systems/{system_uid}"),
        mode=settings.output,
        columns=["hostname", "uid"],
    )


@app.command("tag")
def tag(
    system_uid: str,
    body: Path = typer.Option(..., "--body", exists=True, dir_okay=False),
) -> None:
    settings = resolve_settings()
    payload = json.loads(body.read_text())
    render(
        http.request_json(settings, "PATCH", f"/systems/{system_uid}", json_body=payload),
        mode=settings.output,
    )


@app.command("delete")
def delete(system_uid: str) -> None:
    settings = resolve_settings()
    http.request(settings, "DELETE", f"/systems/{system_uid}")
