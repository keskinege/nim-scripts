from __future__ import annotations

import httpx
import pytest

from nimctl import http
from nimctl.config import GlobalOptions, resolve_settings, set_globals
from nimctl.errors import HttpError, UsageError
from nimctl.pagination import paged_get


def settings(env):
    return resolve_settings()


def test_api_path_includes_version(env):
    assert http.api_path(settings(env), "/systems") == "/api/platform/v1/systems"


def test_basic_auth_header(env, monkeypatch, patched_client):
    monkeypatch.setenv("NIMCTL_USER", "admin")
    fake = patched_client()
    fake.add("GET", "/api/platform/v1/health", {"status": "healthy"})
    http.request_json(settings(env), "GET", "/health")
    assert fake.calls[-1].headers["authorization"].startswith("Basic ")


def test_bearer_takes_precedence(env, monkeypatch, patched_client):
    monkeypatch.setenv("NIMCTL_USER", "admin")
    monkeypatch.setenv("NIMCTL_TOKEN", "eyJhbGci")
    fake = patched_client()
    fake.add("GET", "/api/platform/v1/health", {"status": "healthy"})
    http.request_json(settings(env), "GET", "/health")
    assert fake.calls[-1].headers["authorization"] == "Bearer eyJhbGci"


def test_make_client_sets_verify_timeout_and_auth(env, monkeypatch):
    monkeypatch.setenv("NIMCTL_USER", "admin")
    captured: dict[str, object] = {}
    real_client = httpx.Client

    def spy(**kwargs):
        captured.update(kwargs)
        return real_client(**kwargs)

    monkeypatch.setattr("nimctl.http.httpx.Client", spy)
    http.make_client(settings(env))
    assert captured["verify"] is True
    assert captured["timeout"] == settings(env).timeout
    assert captured["auth"] == ("admin", "x")
    assert captured["base_url"] == "https://nim.test"


def test_make_client_disables_verify_when_insecure(env, monkeypatch):
    set_globals(GlobalOptions(insecure=True))
    captured: dict[str, object] = {}
    real_client = httpx.Client

    def spy(**kwargs):
        captured.update(kwargs)
        return real_client(**kwargs)

    monkeypatch.setattr("nimctl.http.httpx.Client", spy)
    http.make_client(settings(env))
    assert captured["verify"] is False


def test_make_client_trusts_ca_bundle(env, monkeypatch, tmp_path):
    ca = tmp_path / "ca.pem"
    ca.write_text("x")
    set_globals(GlobalOptions(trust=ca))

    class FakeContext:
        def __init__(self):
            self.loaded: str | None = None

        def load_verify_locations(self, *, cafile=None):
            self.loaded = cafile

    fake_context = FakeContext()
    monkeypatch.setattr("nimctl.http.ssl.create_default_context", lambda: fake_context)
    captured: dict[str, object] = {}

    def spy(**kwargs):
        captured.update(kwargs)
        return None

    monkeypatch.setattr("nimctl.http.httpx.Client", spy)
    http.make_client(settings(env))
    # system store kept (create_default_context) AND our CA appended
    assert captured["verify"] is fake_context
    assert fake_context.loaded == str(ca)


def test_insecure_beats_trust(env, monkeypatch, tmp_path):
    ca = tmp_path / "ca.pem"
    ca.write_text("x")
    set_globals(GlobalOptions(trust=ca, insecure=True))
    captured: dict[str, object] = {}
    real_client = httpx.Client

    def spy(**kwargs):
        captured.update(kwargs)
        return real_client(**kwargs)

    monkeypatch.setattr("nimctl.http.httpx.Client", spy)
    http.make_client(settings(env))
    assert captured["verify"] is False


def test_trust_from_env(env, monkeypatch):
    monkeypatch.setenv("NIMCTL_TRUST", "/etc/ssl/ca.pem")
    assert resolve_settings().trust == "/etc/ssl/ca.pem"


def test_missing_trust_file_raises_config_error(env, monkeypatch, tmp_path):
    from nimctl.errors import ConfigError

    set_globals(GlobalOptions(trust=tmp_path / "does-not-exist.pem"))
    with pytest.raises(ConfigError) as excinfo:
        http.make_client(settings(env))
    assert "not found" in str(excinfo.value)


def test_oidc_redirect_is_auth_error(env, patched_client):
    # NIM behind OIDC answers an unauthenticated call with a 302 to the IdP.
    fake = patched_client()
    fake.add(
        "GET",
        "/api/platform/v1/health",
        "",
        status=302,
        headers={"location": "https://keycloak.test/auth/realms/r/protocol/openid-connect/auth"},
    )
    with pytest.raises(HttpError) as excinfo:
        http.request_json(settings(env), "GET", "/health")
    assert excinfo.value.exit_code == 3
    assert "authentication required" in str(excinfo.value)


def test_non_json_200_raises_http_error(env, patched_client):
    fake = patched_client()
    fake.add("GET", "/api/platform/v1/health", "<html>not json</html>")
    with pytest.raises(HttpError) as excinfo:
        http.request_json(settings(env), "GET", "/health")
    assert "non-JSON response" in str(excinfo.value)


def test_redirect_with_token_says_bearer_not_accepted(env, monkeypatch, patched_client):
    monkeypatch.setenv("NIMCTL_TOKEN", "eyJhbGci")
    fake = patched_client()
    fake.add(
        "GET",
        "/api/platform/v1/health",
        "",
        status=302,
        headers={"location": "https://keycloak.test/auth"},
    )
    with pytest.raises(HttpError) as excinfo:
        http.request_json(settings(env), "GET", "/health")
    assert "does not accept a bearer" in str(excinfo.value)
    assert excinfo.value.exit_code == 3


@pytest.mark.parametrize(
    "status,code", [(401, 3), (403, 3), (404, 4), (409, 5), (503, 6), (400, 1)]
)
def test_error_mapping(env, patched_client, status, code):
    fake = patched_client()
    fake.add("GET", "/api/platform/v1/systems", {"code": status, "message": "boom"}, status=status)
    with pytest.raises(HttpError) as excinfo:
        http.request_json(settings(env), "GET", "/systems")
    assert excinfo.value.exit_code == code


def test_error_message_uses_non_json_body(env, patched_client):
    fake = patched_client()
    fake.add("GET", "/api/platform/v1/systems", "upstream exploded", status=500)
    with pytest.raises(HttpError) as excinfo:
        http.request_json(settings(env), "GET", "/systems")
    assert "upstream exploded" in str(excinfo.value)


def test_error_message_with_json_list_body(env, patched_client):
    # An error body that is valid JSON but not an object (e.g. a list) must not crash.
    fake = patched_client()
    fake.add("GET", "/api/platform/v1/systems", ["boom"], status=500)
    with pytest.raises(HttpError) as excinfo:
        http.request_json(settings(env), "GET", "/systems")
    assert excinfo.value.exit_code == 6
    assert "boom" in str(excinfo.value)


def test_method_is_uppercased(env, patched_client):
    fake = patched_client()
    fake.add("GET", "/api/platform/v1/health", {"status": "healthy"})
    http.request_json(settings(env), "get", "/health")
    assert fake.calls[-1].method == "GET"


def test_request_json_returns_none_on_empty_body(env, patched_client):
    fake = patched_client()
    fake.add("DELETE", "/api/platform/v1/systems/sys-1", None, status=204)
    assert http.request_json(settings(env), "DELETE", "/systems/sys-1") is None


def test_raw_path_skips_api_prefix(env, patched_client):
    fake = patched_client()
    fake.add("GET", "/ui/manager.json", {"openapi": "3.0.3"})
    data = http.request_json(settings(env), "GET", "/ui/manager.json", raw_path=True)
    assert data == {"openapi": "3.0.3"}
    assert fake.calls[-1].url.path == "/ui/manager.json"


def test_dest_is_written_atomically(env, patched_client, tmp_path):
    dest = tmp_path / "spec.json"
    fake = patched_client()
    fake.add("GET", "/ui/manager.json", {"ok": True})
    http.request_bytes_to(settings(env), "/ui/manager.json", dest)
    assert dest.exists()
    fake.add("GET", "/ui/manager.json", {"code": 401, "message": "no"}, status=401)
    with pytest.raises(HttpError):
        http.request_bytes_to(settings(env), "/ui/manager.json", dest)
    assert dest.exists()  # previous content preserved


def test_limit_above_100_is_usage_error(env):
    with pytest.raises(UsageError):
        paged_get(settings(env), "/systems", limit=101)


def test_paged_get_sends_params(env, patched_client):
    fake = patched_client()
    fake.add("GET", "/api/platform/v1/systems", {"count": 0, "items": []})
    paged_get(settings(env), "/systems", limit=10, offset=20)
    params = fake.calls[-1].url.params
    assert params["limit"] == "10"
    assert params["offset"] == "20"
