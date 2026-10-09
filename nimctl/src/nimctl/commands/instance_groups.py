from __future__ import annotations

import typer

from .. import http
from ..config import resolve_settings
from ..pagination import paged_get
from ..render import render

app = typer.Typer(no_args_is_help=True, help="Manage NGINX instance groups.")


@app.command("list")
def list_(
    limit: int | None = typer.Option(None, "--limit", min=0, max=100),
    offset: int | None = typer.Option(None, "--offset", min=0),
) -> None:
    settings = resolve_settings()
    render(
        paged_get(settings, "/instance-groups", limit=limit, offset=offset), mode=settings.output
    )


@app.command("get")
def get(inst_group_uid: str) -> None:
    settings = resolve_settings()
    render(
        http.request_json(settings, "GET", f"/instance-groups/{inst_group_uid}"),
        mode=settings.output,
    )


@app.command("summary")
def summary() -> None:
    settings = resolve_settings()
    render(http.request_json(settings, "GET", "/instance-groups/summary"), mode=settings.output)


@app.command("deployment")
def deployment(deployment_uid: str) -> None:
    settings = resolve_settings()
    render(
        http.request_json(settings, "GET", f"/instance-groups/deployments/{deployment_uid}"),
        mode=settings.output,
    )
