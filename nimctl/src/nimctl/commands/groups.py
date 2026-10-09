from __future__ import annotations

import typer

from .. import http
from ..config import resolve_settings
from ..pagination import paged_get
from ..render import render

app = typer.Typer(no_args_is_help=True, help="Manage authentication groups.")


@app.command("list")
def list_(
    limit: int | None = typer.Option(None, "--limit", min=0, max=100),
    offset: int | None = typer.Option(None, "--offset", min=0),
    filter_: str | None = typer.Option(None, "--filter", help="Group name filter."),
) -> None:
    settings = resolve_settings()
    extra = {"groupNameFilter": filter_} if filter_ else None
    render(
        paged_get(settings, "/groups", limit=limit, offset=offset, extra=extra),
        mode=settings.output,
    )


@app.command("get")
def get(group_name: str) -> None:
    settings = resolve_settings()
    render(http.request_json(settings, "GET", f"/groups/{group_name}"), mode=settings.output)
