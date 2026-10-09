from __future__ import annotations

import os
from pathlib import Path

import typer

from .. import http, oidc
from ..config import (
    ContextConfig,
    active_context_name,
    load_config,
    resolve_settings,
    save_config,
)
from ..errors import ConfigError, UsageError
from ..render import render

token_app = typer.Typer(no_args_is_help=True, help="Manage bearer tokens.")


def login() -> None:
    settings = resolve_settings()
    http.request_json(settings, "GET", "/userinfo")
    typer.echo(f"authenticated as {settings.user or '<token>'}", err=True)


def whoami() -> None:
    settings = resolve_settings()
    data = http.request_json(settings, "GET", "/userinfo")
    render(data, mode=settings.output)


def _token_claims(token: str) -> dict[str, object]:
    import base64
    import json

    parts = token.split(".")
    if len(parts) != 3:
        raise UsageError("not a JWT (expected three dot-separated segments)")
    payload = parts[1] + "=" * (-len(parts[1]) % 4)
    try:
        data = json.loads(base64.urlsafe_b64decode(payload))
    except (ValueError, json.JSONDecodeError) as exc:
        raise UsageError(f"could not decode JWT payload: {exc}") from exc
    return data


@token_app.command("claims")
def token_claims(
    file: Path | None = typer.Option(None, "--file", help="Token file (default: the context's)."),
) -> None:
    """Show the claims of the stored (or a given) access token without calling NIM."""
    if file is not None:
        token = file.read_text().strip()
    else:
        settings = resolve_settings()
        if not settings.token:
            raise UsageError("no token in this context; run 'nimctl login-oidc' or 'token set'")
        token = settings.token
    render(_token_claims(token), mode=resolve_settings().output)


def _read_secret(path: Path | None) -> str | None:
    if path is None:
        return None
    if not path.exists():
        raise UsageError(f"secret file not found: {path}")
    return path.read_text().strip()


def _save_token_file(token: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(token)
    os.chmod(path, 0o600)


def _store_secret(context_key: str, path: Path) -> None:
    cfg = load_config()
    name = active_context_name()
    ctx = cfg.contexts.get(name, ContextConfig())
    setattr(ctx, context_key, str(path))
    cfg.contexts[name] = ctx
    save_config(cfg)


def _default_token_path() -> Path:
    base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "nimctl" / "nim.token"


@token_app.command("set")
def token_set(file: Path = typer.Option(..., "--file", exists=True, dir_okay=False)) -> None:
    cfg = load_config()
    name = active_context_name()
    ctx = cfg.contexts.get(name, ContextConfig())
    ctx.token_file = str(file)
    cfg.contexts[name] = ctx
    save_config(cfg)
    typer.echo(f"stored bearer token for context {name}", err=True)


def login_oidc(
    issuer: str | None = typer.Option(None, "--issuer", help="OIDC issuer URL."),
    client_id: str | None = typer.Option(None, "--client-id"),
    client_secret_file: Path | None = typer.Option(
        None, "--client-secret-file", exists=True, dir_okay=False
    ),
    scope: str = typer.Option("openid profile email", "--scope"),
    flow: str = typer.Option("device", "--flow", help="device | code"),
    port: int = typer.Option(
        0, "--port", help="Loopback callback port for --flow code (0 = auto)."
    ),
    no_browser: bool = typer.Option(
        False, "--no-browser", help="Print the URL instead of opening a browser."
    ),
    out: Path | None = typer.Option(None, "--out", help="Where to write the access token."),
    save_context: bool = typer.Option(
        True, "--save/--no-save", help="Also store issuer/client and token path in the context."
    ),
    refresh_out: Path | None = typer.Option(
        None, "--refresh-out", help="Where to write the refresh token."
    ),
) -> None:
    """Log in via OIDC (browser authorization-code or device code) and save the token."""
    settings = resolve_settings()
    issuer = issuer or settings.oidc_issuer
    client_id = client_id or settings.oidc_client_id
    if not issuer or not client_id:
        # NIM redirects to the IdP and names both the issuer and the client.
        found = oidc.discover_from_nim(settings)
        if found:
            issuer = issuer or found[0]
            client_id = client_id or found[1]
            typer.echo(
                f"discovered from {settings.host}: issuer={issuer} client_id={client_id}", err=True
            )
    if not issuer:
        raise ConfigError(
            "could not determine the OIDC issuer: NIM did not redirect to an IdP; "
            "pass --issuer or run 'nimctl context set oidc_issuer <url>'"
        )
    if not client_id:
        raise ConfigError(
            "could not determine the OIDC client id; pass --client-id or run "
            "'nimctl context set oidc_client_id <id>'"
        )
    client_secret = _read_secret(client_secret_file)

    meta = oidc.discover(settings, issuer)
    token_endpoint = meta.get("token_endpoint")
    if not token_endpoint:
        raise ConfigError("issuer has no token_endpoint in its discovery document")

    if flow == "code":
        auth_endpoint = meta.get("authorization_endpoint")
        if not auth_endpoint:
            raise ConfigError("issuer has no authorization_endpoint (needed for --flow code)")
        typer.echo(
            "opening your browser to log in; if it does not open, visit the URL below:",
            err=True,
        )
        tokens = oidc.code_flow(
            settings,
            auth_endpoint,
            token_endpoint,
            client_id,
            scope,
            client_secret=client_secret,
            port=port,
            open_browser=not no_browser,
            notify=lambda url: typer.echo(url, err=True),
        )
    elif flow == "device":
        device_endpoint = meta.get("device_authorization_endpoint")
        if not device_endpoint:
            raise ConfigError("issuer does not support the device-code flow (no device endpoint)")
        dev = oidc.device_authorize(settings, device_endpoint, client_id, scope, client_secret)
        uri = dev.get("verification_uri_complete") or dev.get("verification_uri")
        typer.echo(f"To sign in, open {uri} and enter code: {dev['user_code']}", err=True)
        tokens = oidc.poll_token(
            settings,
            token_endpoint,
            dev["device_code"],
            client_id,
            int(dev.get("interval", 5)),
            int(dev.get("expires_in", 600)),
            client_secret,
        )
    else:
        raise UsageError(f"unknown --flow {flow!r} (choose device or code)")

    dest = out or _default_token_path()
    _save_token_file(tokens["access_token"], dest)
    if tokens.get("refresh_token"):
        _save_token_file(tokens["refresh_token"], refresh_out or dest.with_suffix(".refresh"))

    if save_context:
        cfg = load_config()
        name = active_context_name()
        ctx = cfg.contexts.get(name, ContextConfig())
        ctx.oidc_issuer = issuer
        ctx.oidc_client_id = client_id
        ctx.token_file = str(dest)
        cfg.contexts[name] = ctx
        save_config(cfg)

    typer.echo(f"saved token to {dest}", err=True)


def refresh() -> None:
    """Refresh the stored access token using the saved refresh token."""
    settings = resolve_settings()
    cfg = load_config()
    stored = cfg.contexts.get(active_context_name(), ContextConfig())
    if not stored.token_file:
        raise UsageError("no token_file in this context; run 'nimctl login-oidc' first")
    access_path = Path(stored.token_file)
    refresh_path = access_path.with_suffix(".refresh")
    if not refresh_path.exists():
        raise UsageError(f"no refresh token at {refresh_path}; run 'nimctl login-oidc' first")

    issuer = settings.oidc_issuer
    client_id = settings.oidc_client_id
    if not issuer or not client_id:
        found = oidc.discover_from_nim(settings)
        if found:
            issuer = issuer or found[0]
            client_id = client_id or found[1]
    if not issuer or not client_id:
        raise ConfigError("could not determine the OIDC issuer/client for refresh")

    meta = oidc.discover(settings, issuer)
    tokens = oidc.refresh(settings, meta["token_endpoint"], client_id, refresh_path.read_text())
    _save_token_file(tokens["access_token"], access_path)
    if tokens.get("refresh_token"):
        _save_token_file(tokens["refresh_token"], refresh_path)
    typer.echo(f"refreshed token at {access_path}", err=True)
