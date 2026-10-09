"""Minimal OIDC helpers for login: discovery, device authorization, polling, refresh.

nimctl only needs to turn Keycloak into a JWT; there is no general OIDC plumbing here.
"""

from __future__ import annotations

import base64
import hashlib
import os
import threading
import time
import webbrowser
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

from . import http
from .config import Settings
from .errors import ConfigError, HttpError

DEVICE_GRANT = "urn:ietf:params:oauth:grant-type:device_code"
_AUTH_SUFFIX = "/protocol/openid-connect/auth"
CALLBACK_PATH = "/callback"


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _client(settings: Settings) -> httpx.Client:
    # Reuses nimctl's TLS policy (--trust / --insecure) and the test transport, but
    # talks to the IdP, not NIM, so it carries no NIM auth.
    return httpx.Client(
        verify=http.verify_setting(settings),
        timeout=settings.timeout,
        transport=http._TEST_TRANSPORT,
    )


def _error(r: httpx.Response) -> str:
    try:
        body = r.json()
    except ValueError:
        body = None
    if isinstance(body, dict):
        return body.get("error_description") or body.get("error") or r.text
    return r.text


def discover(settings: Settings, issuer: str) -> dict[str, Any]:
    url = issuer.rstrip("/") + "/.well-known/openid-configuration"
    with _client(settings) as client:
        r = client.get(url)
        if r.status_code >= 400:
            raise HttpError(r.status_code, _error(r))
        return r.json()


def discover_from_nim(settings: Settings) -> tuple[str, str | None] | None:
    """Derive (issuer, client_id) from NIM's own redirect to the IdP.

    An unauthenticated request to NIM returns 302 to the IdP's authorization
    endpoint, e.g.:

        Location: https://idp/auth/realms/my-realm/protocol/openid-connect/auth
                  ?client_id=my-client&response_type=code&...

    The issuer is that URL up to ``/protocol/openid-connect/auth``; the client id
    is the ``client_id`` query parameter. Returns None when NIM is not OIDC-fronted
    (e.g. Basic auth -> 401 with no redirect).
    """
    with _client(settings) as client:
        r = client.get(settings.host, follow_redirects=False)
    location = r.headers.get("location")
    if not location:
        return None
    parsed = urlparse(location)
    index = parsed.path.find(_AUTH_SUFFIX)
    if index == -1:
        return None
    issuer = f"{parsed.scheme}://{parsed.netloc}{parsed.path[:index]}"
    client_id = (parse_qs(parsed.query).get("client_id") or [None])[0]
    return issuer, client_id


def device_authorize(
    settings: Settings,
    device_endpoint: str,
    client_id: str,
    scope: str,
    client_secret: str | None = None,
) -> dict[str, Any]:
    data = {"client_id": client_id, "scope": scope}
    if client_secret:
        data["client_secret"] = client_secret
    with _client(settings) as client:
        r = client.post(device_endpoint, data=data)
        if r.status_code >= 400:
            raise HttpError(r.status_code, _error(r))
        return r.json()


def _token_request(settings: Settings, endpoint: str, data: dict[str, str]) -> httpx.Response:
    with _client(settings) as client:
        return client.post(endpoint, data=data)


def poll_token(
    settings: Settings,
    token_endpoint: str,
    device_code: str,
    client_id: str,
    interval: int,
    expires_in: int,
    client_secret: str | None = None,
    *,
    sleep=time.sleep,
    clock=time.monotonic,
) -> dict[str, Any]:
    deadline = clock() + max(expires_in, 1)
    wait = max(interval, 1)
    while True:
        data = {
            "grant_type": DEVICE_GRANT,
            "device_code": device_code,
            "client_id": client_id,
        }
        if client_secret:
            data["client_secret"] = client_secret
        r = _token_request(settings, token_endpoint, data)
        if r.status_code == 200:
            return r.json()
        try:
            err = r.json().get("error")
        except ValueError:
            err = None
        if err == "slow_down":
            wait += 5
        elif err not in ("authorization_pending", None):
            raise ConfigError(f"OIDC device login failed: {_error(r)}")
        if clock() >= deadline:
            raise ConfigError("OIDC device login timed out")
        sleep(wait)


def refresh(
    settings: Settings,
    token_endpoint: str,
    client_id: str,
    refresh_token: str,
    client_secret: str | None = None,
) -> dict[str, Any]:
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": client_id,
    }
    if client_secret:
        data["client_secret"] = client_secret
    r = _token_request(settings, token_endpoint, data)
    if r.status_code >= 400:
        raise HttpError(r.status_code, _error(r))
    return r.json()


# --- authorization-code + PKCE (browser) ------------------------------------


def pkce_pair() -> tuple[str, str]:
    """Return (code_verifier, code_challenge) for S256 PKCE."""
    verifier = _b64url(os.urandom(32))
    challenge = _b64url(hashlib.sha256(verifier.encode()).digest())
    return verifier, challenge


def authorize_url(
    auth_endpoint: str, client_id: str, redirect_uri: str, scope: str, state: str, challenge: str
) -> str:
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": scope,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    return f"{auth_endpoint}?{urlencode(params)}"


def parse_callback(query: str) -> dict[str, str | None]:
    qs = parse_qs(query)

    def first(key: str) -> str | None:
        return (qs.get(key) or [None])[0]

    return {
        "code": first("code"),
        "state": first("state"),
        "error": first("error"),
        "error_description": first("error_description"),
    }


def _token_error(r: httpx.Response, client_id: str) -> Exception:
    try:
        body = r.json()
    except ValueError:
        body = {}
    code = body.get("error") if isinstance(body, dict) else None
    if code == "unauthorized_client":
        return ConfigError(
            f"client authentication failed for {client_id!r}: it is a confidential client. "
            "Pass --client-secret-file <path>, or use a public client (one with no secret)."
        )
    return HttpError(r.status_code, _error(r))


def exchange_code(
    settings: Settings,
    token_endpoint: str,
    client_id: str,
    code: str,
    redirect_uri: str,
    verifier: str,
    client_secret: str | None = None,
) -> dict[str, Any]:
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": client_id,
        "code_verifier": verifier,
    }
    if client_secret:
        data["client_secret"] = client_secret
    r = _token_request(settings, token_endpoint, data)
    if r.status_code >= 400:
        raise _token_error(r, client_id)
    return r.json()


class _CallbackServer(HTTPServer):
    callback_path: str
    result: dict[str, str | None] | None
    done: threading.Event


class _CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        server: _CallbackServer = self.server  # type: ignore[assignment]
        parsed = urlparse(self.path)
        if parsed.path != server.callback_path:
            self.send_response(404)
            self.end_headers()
            return
        server.result = parse_callback(parsed.query)
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(
            b"<html><body><h3>Login complete</h3>You can close this tab.</body></html>"
        )
        server.done.set()

    def log_message(self, *args: Any) -> None:  # silence the default stderr spam
        return


def code_flow(
    settings: Settings,
    auth_endpoint: str,
    token_endpoint: str,
    client_id: str,
    scope: str,
    *,
    client_secret: str | None = None,
    port: int = 0,
    open_browser: bool = True,
    timeout: int = 300,
    notify: Callable[[str], None] | None = None,
    on_redirect_uri: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Run authorization-code + PKCE with a 127.0.0.1 loopback redirect."""
    verifier, challenge = pkce_pair()
    state = _b64url(os.urandom(16))
    httpd = _CallbackServer(("127.0.0.1", port), _CallbackHandler)
    httpd.callback_path = CALLBACK_PATH
    httpd.result = None
    httpd.done = threading.Event()
    bound_port = httpd.server_address[1]
    redirect_uri = f"http://127.0.0.1:{bound_port}{CALLBACK_PATH}"
    if on_redirect_uri:
        on_redirect_uri(redirect_uri)
    url = authorize_url(auth_endpoint, client_id, redirect_uri, scope, state, challenge)

    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    if notify:
        notify(url)
    if open_browser:
        webbrowser.open(url)
    try:
        if not httpd.done.wait(timeout):
            raise ConfigError("timed out waiting for the browser login")
    finally:
        httpd.shutdown()

    result = httpd.result or {}
    if result.get("error"):
        raise ConfigError(f"login failed: {result.get('error_description') or result['error']}")
    if result.get("state") != state:
        raise ConfigError("state mismatch (possible CSRF); aborted")
    code = result.get("code")
    if not code:
        raise ConfigError("no authorization code returned by the IdP")
    return exchange_code(
        settings, token_endpoint, client_id, code, redirect_uri, verifier, client_secret
    )
