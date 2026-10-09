from __future__ import annotations

from dataclasses import fields

import typer

from ..config import (
    ContextConfig,
    active_context_name,
    config_path,
    load_config,
    save_config,
    validate_context_name,
)
from ..errors import UsageError

app = typer.Typer(no_args_is_help=True, help="Manage connection contexts.")

_ALLOWED_KEYS = {item.name for item in fields(ContextConfig)}


def _parse_value(key: str, value: str) -> object:
    if key == "insecure":
        lowered = value.lower()
        if lowered in {"true", "1", "yes", "on"}:
            return True
        if lowered in {"false", "0", "no", "off"}:
            return False
        raise UsageError("insecure must be true or false")
    return value


@app.command("list")
def list_() -> None:
    cfg = load_config()
    for name in sorted(cfg.contexts):
        typer.echo(name)


@app.command("use")
def use(name: str) -> None:
    validate_context_name(name)
    cfg = load_config()
    if name not in cfg.contexts:
        raise UsageError(f"no such context: {name}")
    cfg.current_context = name
    save_config(cfg)
    typer.echo(f"active context: {name}", err=True)


@app.command("set")
def set_(key: str, value: str) -> None:
    if key not in _ALLOWED_KEYS:
        allowed = ", ".join(sorted(_ALLOWED_KEYS))
        raise UsageError(f"unknown context key: {key} (allowed: {allowed})")
    cfg = load_config()
    name = active_context_name()
    stored = cfg.contexts.get(name, ContextConfig())
    setattr(stored, key, _parse_value(key, value))
    cfg.contexts[name] = stored
    save_config(cfg)
    typer.echo(f"{name}.{key} = {value}", err=True)


@app.command("show")
def show() -> None:
    cfg = load_config()
    name = active_context_name()
    stored = cfg.contexts.get(name, ContextConfig())
    typer.echo(f"[{name}]")
    data = {
        "host": stored.host,
        "api_version": stored.api_version,
        "user": stored.user,
        "password_file": stored.password_file,
        "token_file": stored.token_file,
        "trust": stored.trust,
        "oidc_issuer": stored.oidc_issuer,
        "oidc_client_id": stored.oidc_client_id,
        "insecure": stored.insecure,
    }
    for key, value in data.items():
        if value not in (None, False):
            typer.echo(f"{key} = {value}")


@app.command("delete")
def delete(name: str) -> None:
    validate_context_name(name)
    cfg = load_config()
    if name not in cfg.contexts:
        raise UsageError(f"no such context: {name}")
    del cfg.contexts[name]
    if cfg.current_context == name:
        cfg.current_context = None
    save_config(cfg)


@app.command("path")
def path() -> None:
    typer.echo(config_path())
