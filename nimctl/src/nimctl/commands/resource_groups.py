from __future__ import annotations

import typer

from .. import http
from ..config import resolve_settings
from ..pagination import paged_get
from ..render import render

app = typer.Typer(no_args_is_help=True, help="Manage resource groups.")


@app.command("list")
def list_(
    limit: int | None = typer.Option(None, "--limit", min=0, max=100),
    offset: int | None = typer.Option(None, "--offset", min=0),
    show_details: bool = typer.Option(False, "--show-details"),
    name_filter: str | None = typer.Option(
        None, "--name-filter", help="Resource group name filter."
    ),
) -> None:
    settings = resolve_settings()
    extra: dict[str, str] = {}
    if show_details:
        extra["showDetails"] = "true"
    if name_filter:
        extra["resourceGroupNameFilter"] = name_filter
    render(
        paged_get(settings, "/resource-groups", limit=limit, offset=offset, extra=extra or None),
        mode=settings.output,
    )


@app.command("get")
def get(resource_group_uid: str) -> None:
    settings = resolve_settings()
    render(
        http.request_json(settings, "GET", f"/resource-groups/{resource_group_uid}"),
        mode=settings.output,
    )
