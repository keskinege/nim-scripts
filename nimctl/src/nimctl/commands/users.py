from __future__ import annotations

import json
from pathlib import Path

import typer

from .. import http
from ..config import resolve_settings
from ..pagination import paged_get
from ..render import render

app = typer.Typer(no_args_is_help=True, help="Manage users.")


@app.command("list")
def list_(
    limit: int | None = typer.Option(None, "--limit", min=0, max=100),
    offset: int | None = typer.Option(None, "--offset", min=0),
    source: str | None = typer.Option(None, "--source"),
) -> None:
    settings = resolve_settings()
    extra = {"source": source} if source else None
    render(
        paged_get(settings, "/users", limit=limit, offset=offset, extra=extra), mode=settings.output
    )


@app.command("get")
def get(user_name: str) -> None:
    settings = resolve_settings()
    render(http.request_json(settings, "GET", f"/users/{user_name}"), mode=settings.output)


@app.command("create")
def create(body: Path = typer.Option(..., "--body", exists=True, dir_okay=False)) -> None:
    settings = resolve_settings()
    payload = json.loads(body.read_text())
    render(http.request_json(settings, "POST", "/users", json_body=payload), mode=settings.output)


@app.command("delete")
def delete(user_name: str) -> None:
    settings = resolve_settings()
    http.request(settings, "DELETE", f"/users/{user_name}")
