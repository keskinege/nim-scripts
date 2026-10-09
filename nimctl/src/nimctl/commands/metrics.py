from __future__ import annotations

import typer

from .. import http
from ..config import resolve_settings
from ..render import render

app = typer.Typer(no_args_is_help=True, help="Query metrics.")


@app.command("query")
def query(
    names: str = typer.Option(..., "--names"),
    start_time: str | None = typer.Option(None, "--start-time"),
    end_time: str | None = typer.Option(None, "--end-time"),
    resolution: str | None = typer.Option(None, "--resolution"),
    filter_: str | None = typer.Option(None, "--filter"),
    group_by: str | None = typer.Option(None, "--group-by"),
    dimensions: str | None = typer.Option(None, "--dimensions"),
) -> None:
    settings = resolve_settings()
    params: dict[str, str] = {"names": names}
    if start_time:
        params["startTime"] = start_time
    if end_time:
        params["endTime"] = end_time
    if resolution:
        params["resolution"] = resolution
    if filter_:
        params["filter"] = filter_
    if group_by:
        params["groupBy"] = group_by
    if dimensions:
        params["dimensions"] = dimensions
    render(
        http.request_json(settings, "GET", "/analytics/metrics", params=params),
        mode=settings.output,
    )
