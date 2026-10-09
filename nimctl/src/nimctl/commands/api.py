from __future__ import annotations

import json
from pathlib import Path

import typer

from .. import http, spec
from ..config import resolve_settings
from ..errors import UsageError
from ..render import render

app = typer.Typer(no_args_is_help=True, help="Raw API passthrough and OpenAPI introspection.")


def _parse_query(items: list[str]) -> dict[str, str] | None:
    if not items:
        return None
    params: dict[str, str] = {}
    for item in items:
        key, sep, value = item.partition("=")
        if not sep or not key:
            raise UsageError(f"invalid --query {item!r}: expected key=value")
        params[key] = value
    return params


@app.command("call")
def call(
    method: str,
    path: str,
    body_file: Path | None = typer.Option(None, "--body", exists=True, dir_okay=False),
    query: list[str] = typer.Option(
        [], "--query", "-q", help="Query parameter as key=value (repeatable)."
    ),
) -> None:
    settings = resolve_settings()
    body = json.loads(body_file.read_text()) if body_file else None
    data = http.request_json(
        settings, method.upper(), path, json_body=body, params=_parse_query(query)
    )
    render(data, mode=settings.output)


@app.command("paths")
def paths(tag: str) -> None:
    settings = resolve_settings()
    document = spec.fetch_spec(settings)
    for method, path in spec.api_paths(document, tag):
        typer.echo(f"{method}\t{path}")


@app.command("tags")
def tags() -> None:
    settings = resolve_settings()
    for tag in spec.api_tags(spec.fetch_spec(settings)):
        typer.echo(tag)


@app.command("spec")
def show_spec() -> None:
    settings = resolve_settings()
    render(spec.fetch_spec(settings), mode="json")
