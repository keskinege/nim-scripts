from __future__ import annotations

import base64
import json
import os
import time
from pathlib import Path

import typer

from .. import http
from ..config import Settings, resolve_settings
from ..errors import ConfigError, DeploymentFailed
from ..render import render

app = typer.Typer(no_args_is_help=True, help="Manage NGINX configurations.")

_TERMINAL = {"successful", "failed", "degraded"}


def wait_for_deployment(settings: Settings, deployment_uid: str) -> None:
    interval = float(os.environ.get("NIMCTL_POLL_INTERVAL", "2"))
    attempts = int(os.environ.get("NIMCTL_WAIT_ATTEMPTS", "60"))
    for _ in range(attempts):
        data = http.request_json(
            settings, "GET", f"/systems/instances/deployments/{deployment_uid}"
        )
        status = (data or {}).get("status")
        if status == "successful":
            render(data, mode=settings.output)
            return
        if status in _TERMINAL:
            render(data, mode=settings.output)
            raise DeploymentFailed(f"deployment {deployment_uid} {status}")
        time.sleep(interval)
    raise ConfigError(f"timed out waiting for deployment {deployment_uid}")


@app.command("get")
def get(
    system_uid: str,
    nginx_uid: str,
    decode: str | None = typer.Option(
        None, "--decode", help="Print one config file's decoded contents."
    ),
) -> None:
    settings = resolve_settings()
    data = http.request_json(settings, "GET", f"/systems/{system_uid}/instances/{nginx_uid}/config")
    if decode is None:
        render(data, mode=settings.output)
        return
    for entry in data.get("configFiles", []):
        if entry.get("name") == decode:
            typer.echo(base64.b64decode(entry["contents"]).decode())
            return
    raise ConfigError(f"config file not found: {decode}")


@app.command("publish")
def publish(
    system_uid: str,
    nginx_uid: str,
    body: Path = typer.Option(..., "--body", exists=True, dir_okay=False),
    wait: bool = typer.Option(False, "--wait"),
) -> None:
    settings = resolve_settings()
    data = http.request_json(
        settings,
        "POST",
        f"/systems/{system_uid}/instances/{nginx_uid}/config",
        json_body=json.loads(body.read_text()),
    )
    if wait and data and data.get("deploymentUID"):
        wait_for_deployment(settings, data["deploymentUID"])
    else:
        render(data, mode=settings.output)


@app.command("deployment")
def deployment(deployment_uid: str) -> None:
    settings = resolve_settings()
    render(
        http.request_json(settings, "GET", f"/systems/instances/deployments/{deployment_uid}"),
        mode=settings.output,
    )
