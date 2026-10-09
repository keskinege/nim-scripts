from __future__ import annotations

import json
import ssl
from pathlib import Path
from typing import Any

import httpx

from .config import Settings
from .errors import ConfigError, HttpError

_TEST_TRANSPORT: httpx.BaseTransport | None = None


def api_path(settings: Settings, path: str) -> str:
    return f"/api/platform/{settings.api_version}{path}"


def verify_setting(settings: Settings) -> bool | ssl.SSLContext:
    """TLS verification for a client: off, a trusted CA bundle, or system defaults."""
    if settings.insecure:
        return False
    if settings.trust:
        if not Path(settings.trust).is_file():
            raise ConfigError(
                f"--trust file not found: {settings.trust} "
                "(set with 'nimctl context set trust <path>' or NIMCTL_TRUST)"
            )
        # Keep the system trust store AND add the given CA/PEM (which may hold
        # several certs, e.g. a self-signed NIM plus an internal CA).
        context = ssl.create_default_context()
        try:
            context.load_verify_locations(cafile=settings.trust)
        except ssl.SSLError as exc:
            raise ConfigError(f"could not load --trust {settings.trust}: {exc}") from exc
        return context
    return True


def make_client(settings: Settings) -> httpx.Client:
    headers = {"Accept": "application/json"}
    auth: tuple[str, str] | None = None
    if settings.token:
        headers["Authorization"] = f"Bearer {settings.token}"
    elif settings.user is not None:
        auth = (settings.user, settings.password or "")
    return httpx.Client(
        base_url=settings.host,
        verify=verify_setting(settings),
        headers=headers,
        auth=auth,
        timeout=settings.timeout,
        transport=_TEST_TRANSPORT,
    )


def _raise(resp: httpx.Response) -> None:
    try:
        body = resp.json()
    except (json.JSONDecodeError, ValueError):
        body = None
    if not isinstance(body, dict):
        body = None
    message = (body or {}).get("message") or resp.text
    raise HttpError(resp.status_code, message or "")


def request(
    settings: Settings,
    method: str,
    path: str,
    *,
    json_body: Any = None,
    params: dict[str, Any] | None = None,
    raw_path: bool = False,
    dest: Path | None = None,
) -> httpx.Response | None:
    with make_client(settings) as client:
        url = path if raw_path else api_path(settings, path)
        resp = client.request(method.upper(), url, json=json_body, params=params)
        if 300 <= resp.status_code < 400:
            # NIM behind OIDC redirects to the IdP when the edge will not accept the
            # request. This endpoint does not accept a bearer Authorization header at all:
            # a valid token, a bogus one and no credentials all get the identical 302.
            loc = resp.headers.get("location", "")
            if settings.token:
                detail = (
                    "request redirected to the IdP: this endpoint does not accept a bearer "
                    "Authorization header (a valid token, a bogus one and no token all redirect "
                    "alike). It likely requires an OIDC browser session cookie; to use a token "
                    "the server must be configured to validate bearer JWTs on this API path"
                )
            else:
                detail = "authentication required"
            raise HttpError(resp.status_code, f"{detail} (redirect to {loc})".strip())
        if resp.status_code >= 400:
            _raise(resp)
        if dest is not None:
            _atomic_write_bytes(dest, resp.content)
            return None
        return resp


def request_json(settings: Settings, method: str, path: str, **kwargs: Any) -> Any:
    resp = request(settings, method, path, **kwargs)
    if resp is None or not resp.content:
        return None
    try:
        return resp.json()
    except ValueError as exc:
        raise HttpError(resp.status_code, f"non-JSON response: {resp.text[:200]}") from exc


def request_text(settings: Settings, method: str, path: str, **kwargs: Any) -> str:
    resp = request(settings, method, path, **kwargs)
    return resp.text if resp is not None else ""


def request_bytes_to(settings: Settings, path: str, dest: Path, *, raw_path: bool = True) -> None:
    request(settings, "GET", path, raw_path=raw_path, dest=dest)


def _atomic_write_bytes(dest: Path, data: bytes) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    try:
        tmp.write_bytes(data)
        tmp.replace(dest)
    finally:
        if tmp.exists():
            tmp.unlink()
