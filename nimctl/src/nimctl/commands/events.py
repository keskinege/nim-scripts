from __future__ import annotations

import typer

from .. import http
from ..config import resolve_settings
from ..render import render

app = typer.Typer(no_args_is_help=True, help="Query analytics events.")


@app.command("list")
def list_(
    start_time: str | None = typer.Option(None, "--start-time"),
    end_time: str | None = typer.Option(None, "--end-time"),
    filter_: str | None = typer.Option(None, "--filter"),
    order_by: str | None = typer.Option(None, "--order-by"),
    page_size: int | None = typer.Option(None, "--page-size", min=0, max=100),
    include_total: bool = typer.Option(False, "--include-total"),
) -> None:
    settings = resolve_settings()
    params: dict[str, str] = {}
    if start_time:
        params["startTime"] = start_time
    if end_time:
        params["endTime"] = end_time
    if filter_:
        params["filter"] = filter_
    if order_by:
        params["orderBy"] = order_by
    if page_size is not None:
        params["pageSize"] = str(page_size)
    if include_total:
        params["includeTotal"] = "true"
    render(
        http.request_json(settings, "GET", "/analytics/events", params=params or None),
        mode=settings.output,
    )


@app.command("get")
def get(event_id: str) -> None:
    settings = resolve_settings()
    render(
        http.request_json(settings, "GET", f"/analytics/events/{event_id}"),
        mode=settings.output,
    )
