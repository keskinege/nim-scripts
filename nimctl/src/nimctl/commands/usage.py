from __future__ import annotations

from pathlib import Path

import typer

from .. import http
from ..config import resolve_settings
from ..pagination import paged_get
from ..render import render

app = typer.Typer(no_args_is_help=True, help="Query NGINX usage telemetry.")


@app.command("records")
def records(
    limit: int | None = typer.Option(None, "--limit", min=0, max=100),
    offset: int | None = typer.Option(None, "--offset", min=0),
    nginx_uid: str | None = typer.Option(None, "--nginx-uid"),
    from_: str | None = typer.Option(None, "--from"),
    to: str | None = typer.Option(None, "--to"),
) -> None:
    settings = resolve_settings()
    params: dict[str, object] = {}
    if nginx_uid:
        params["nginxUid"] = nginx_uid
    if from_:
        params["from"] = from_
    if to:
        params["to"] = to
    data = paged_get(settings, "/usage-records", limit=limit, offset=offset, extra=params)
    render(data, mode=settings.output)


@app.command("export")
def export(out: Path | None = typer.Option(None, "--out", dir_okay=True)) -> None:
    settings = resolve_settings()
    text = http.request_text(settings, "GET", "/usage-records/export")
    if out is None:
        typer.echo(text, nl=False)
        return
    out.write_text(text)
    typer.echo(f"wrote {out}", err=True)


@app.command("data")
def data() -> None:
    settings = resolve_settings()
    render(http.request_json(settings, "GET", "/usage-data"), mode=settings.output)
