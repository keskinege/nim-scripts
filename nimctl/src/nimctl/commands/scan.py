from __future__ import annotations

import os
import time

import typer

from .. import http
from ..config import Settings, resolve_settings
from ..errors import ConfigError
from ..render import render

app = typer.Typer(no_args_is_help=True, help="Scan for NGINX instances.")

_TERMINAL = {"complete", "error", "cancelled"}


def wait_for_scan(settings: Settings) -> None:
    interval = float(os.environ.get("NIMCTL_POLL_INTERVAL", "2"))
    attempts = int(os.environ.get("NIMCTL_WAIT_ATTEMPTS", "300"))
    for _ in range(attempts):
        data = http.request_json(settings, "GET", "/servers/scan")
        status = (data or {}).get("status")
        if status in _TERMINAL:
            render(data, mode=settings.output)
            return
        time.sleep(interval)
    raise ConfigError("timed out waiting for scan")


@app.command("start")
def start(
    subnet: str,
    port: int | None = typer.Option(None, "--port"),
    wait: bool = typer.Option(False, "--wait"),
) -> None:
    settings = resolve_settings()
    body: dict[str, object] = {"subnet": subnet}
    if port is not None:
        body["ports"] = [port]
    data = http.request_json(settings, "POST", "/servers/scan", json_body=body)
    if wait:
        wait_for_scan(settings)
    else:
        render(data, mode=settings.output)


@app.command("status")
def status() -> None:
    settings = resolve_settings()
    render(http.request_json(settings, "GET", "/servers/scan"), mode=settings.output)


@app.command("cancel")
def cancel() -> None:
    settings = resolve_settings()
    http.request(settings, "DELETE", "/servers/scan")
