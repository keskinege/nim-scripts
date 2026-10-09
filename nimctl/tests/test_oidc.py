from __future__ import annotations

from nimctl.cli import main

OIDC_META = {
    "issuer": "https://kc.test/auth/realms/r",
    "device_authorization_endpoint": "https://kc.test/auth/realms/r/protocol/openid-connect/auth/device",
    "token_endpoint": "https://kc.test/auth/realms/r/protocol/openid-connect/token",
}


def test_discover(env, patched_client):
    from nimctl import oidc
    from nimctl.config import resolve_settings

    fake = patched_client()
    fake.add("GET", "/auth/realms/r/.well-known/openid-configuration", OIDC_META)
    # issuer hosts differ from NIM base_url, so route on the full path of the issuer host
    meta = oidc.discover(resolve_settings(), "https://nim.test/auth/realms/r")
    assert meta["token_endpoint"] == OIDC_META["token_endpoint"]


def test_discover_from_nim_reads_redirect(env, patched_client):
    from nimctl import oidc
    from nimctl.config import resolve_settings

    location = (
        "https://kc.test/auth/realms/my-realm/protocol/openid-connect/auth"
        "?response_type=code&scope=openid&client_id=my-client&redirect_uri=https%3A%2F%2Fnim.test%2F_codexch"
    )
    fake = patched_client()
    fake.add("GET", "/", "", status=302, headers={"location": location})
    assert oidc.discover_from_nim(resolve_settings()) == (
        "https://kc.test/auth/realms/my-realm",
        "my-client",
    )


def test_discover_from_nim_none_when_basic(env, patched_client):
    from nimctl import oidc
    from nimctl.config import resolve_settings

    fake = patched_client()
    fake.add("GET", "/", "", status=401, headers={"www-authenticate": "Basic"})
    assert oidc.discover_from_nim(resolve_settings()) is None


def test_login_oidc_derives_issuer_and_client(env, patched_client, tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    fake = patched_client()
    fake.add(
        "GET",
        "/",
        "",
        status=302,
        headers={
            "location": "https://nim.test/auth/realms/r/protocol/openid-connect/auth"
            "?client_id=my-client&response_type=code"
        },
    )
    fake.add("GET", "/auth/realms/r/.well-known/openid-configuration", OIDC_META)
    fake.add(
        "POST",
        "/auth/realms/r/protocol/openid-connect/auth/device",
        {
            "device_code": "D",
            "user_code": "CODE-1234",
            "verification_uri": "https://nim.test/device",
            "interval": 1,
            "expires_in": 30,
        },
    )
    fake.add("POST", "/auth/realms/r/protocol/openid-connect/token", {"access_token": "AT"})
    dest = tmp_path / "tok.jwt"
    # no --issuer / --client-id: both must be derived from NIM's redirect
    rc = main(["--context", "default", "login-oidc", "--out", str(dest), "--no-save"])
    assert rc == 0
    assert dest.read_text() == "AT"


def test_login_oidc_without_redirect_errors(env, patched_client, tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    fake = patched_client()
    fake.add("GET", "/", "", status=401, headers={"www-authenticate": "Basic"})
    rc = main(["login-oidc", "--out", str(tmp_path / "t.jwt"), "--no-save"])
    assert rc == 1
    assert "could not determine the OIDC issuer" in capsys.readouterr().err


def test_pkce_pair_matches_s256():
    import base64
    import hashlib

    from nimctl import oidc

    verifier, challenge = oidc.pkce_pair()
    expected = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
    assert challenge == expected.rstrip(b"=").decode()


def test_authorize_url_has_pkce_state_code():
    from nimctl import oidc

    url = oidc.authorize_url(
        "https://idp/auth", "cid", "http://127.0.0.1:9999/callback", "openid", "ST", "CH"
    )
    assert "response_type=code" in url
    assert "code_challenge=CH" in url
    assert "code_challenge_method=S256" in url
    assert "state=ST" in url
    assert "client_id=cid" in url


def test_parse_callback():
    from nimctl import oidc

    assert oidc.parse_callback("code=ABC&state=S")["code"] == "ABC"
    assert (
        oidc.parse_callback("error=access_denied&error_description=nope")["error"]
        == "access_denied"
    )


def test_exchange_code_posts_verifier(env, patched_client):
    from nimctl import oidc
    from nimctl.config import resolve_settings

    fake = patched_client()
    fake.add("POST", "/token", {"access_token": "AT", "refresh_token": "RT"})
    toks = oidc.exchange_code(
        resolve_settings(),
        "https://nim.test/token",
        "cid",
        "CODE",
        "http://127.0.0.1:1/callback",
        "VER",
    )
    body = fake.calls[-1].content.decode()
    assert "grant_type=authorization_code" in body
    assert "code_verifier=VER" in body
    assert toks["access_token"] == "AT"


def test_exchange_code_confidential_client_hint(env, patched_client):
    import pytest

    from nimctl import oidc
    from nimctl.config import resolve_settings
    from nimctl.errors import ConfigError

    fake = patched_client()
    fake.add(
        "POST",
        "/token",
        {
            "error": "unauthorized_client",
            "error_description": "Invalid client or Invalid client credentials",
        },
        status=401,
    )
    with pytest.raises(ConfigError) as excinfo:
        oidc.exchange_code(
            resolve_settings(),
            "https://nim.test/token",
            "my-client",
            "CODE",
            "http://127.0.0.1:1/callback",
            "VER",
        )
    assert "confidential client" in str(excinfo.value)


def test_code_flow_full_roundtrip(env, patched_client, monkeypatch):
    import urllib.request
    from urllib.parse import parse_qs, urlparse

    from nimctl import oidc
    from nimctl.config import resolve_settings

    fake = patched_client()
    fake.add("POST", "/token", {"access_token": "AT"})

    def fake_open(url: str) -> bool:
        # act as the browser: log in at the IdP, then hit the loopback redirect
        q = parse_qs(urlparse(url).query)
        redirect = q["redirect_uri"][0]
        state = q["state"][0]
        urllib.request.urlopen(f"{redirect}?code=THECODE&state={state}", timeout=5).read()
        return True

    monkeypatch.setattr(oidc.webbrowser, "open", fake_open)
    toks = oidc.code_flow(
        resolve_settings(),
        "https://nim.test/auth",
        "https://nim.test/token",
        "cid",
        "openid",
        timeout=15,
    )
    assert toks["access_token"] == "AT"
    body = fake.calls[-1].content.decode()
    assert "code=THECODE" in body


def test_code_flow_state_mismatch(env, patched_client, monkeypatch):
    import urllib.request
    from urllib.parse import parse_qs, urlparse

    import pytest

    from nimctl import oidc
    from nimctl.config import resolve_settings
    from nimctl.errors import ConfigError

    patched_client()

    def fake_open(url: str) -> bool:
        q = parse_qs(urlparse(url).query)
        redirect = q["redirect_uri"][0]
        urllib.request.urlopen(f"{redirect}?code=X&state=WRONG", timeout=5).read()
        return True

    monkeypatch.setattr(oidc.webbrowser, "open", fake_open)
    with pytest.raises(ConfigError):
        oidc.code_flow(
            resolve_settings(),
            "https://nim.test/auth",
            "https://nim.test/token",
            "cid",
            "openid",
            timeout=15,
        )


def test_device_authorize_sends_client(env, patched_client):
    from nimctl import oidc
    from nimctl.config import resolve_settings

    fake = patched_client()
    fake.add(
        "POST",
        "/auth/realms/r/protocol/openid-connect/auth/device",
        {
            "device_code": "D",
            "user_code": "ABCD-EFGH",
            "verification_uri": "https://kc.test/device",
            "interval": 1,
            "expires_in": 30,
        },
    )
    dev = oidc.device_authorize(
        resolve_settings(),
        "https://nim.test/auth/realms/r/protocol/openid-connect/auth/device",
        "cliapp",
        "openid",
    )
    assert dev["user_code"] == "ABCD-EFGH"
    body = fake.calls[-1].content.decode()
    assert "client_id=cliapp" in body


def test_poll_token_pending_then_ok(env, patched_client):
    from nimctl import oidc
    from nimctl.config import resolve_settings

    fake = patched_client()
    endpoint = "/auth/realms/r/protocol/openid-connect/token"
    fake.add_sequence(
        "POST",
        endpoint,
        [
            (400, {"error": "authorization_pending"}),
            (200, {"access_token": "AT", "refresh_token": "RT"}),
        ],
    )
    toks = oidc.poll_token(
        resolve_settings(),
        "https://nim.test" + endpoint,
        "D",
        "cliapp",
        1,
        30,
        sleep=lambda _s: None,
        clock=lambda: 0,
    )
    assert toks["access_token"] == "AT"


def test_poll_token_slow_down_then_ok(env, patched_client):
    from nimctl import oidc
    from nimctl.config import resolve_settings

    fake = patched_client()
    endpoint = "/auth/realms/r/protocol/openid-connect/token"
    fake.add_sequence(
        "POST",
        endpoint,
        [
            (400, {"error": "slow_down"}),
            (200, {"access_token": "AT"}),
        ],
    )
    toks = oidc.poll_token(
        resolve_settings(),
        "https://nim.test" + endpoint,
        "D",
        "cliapp",
        1,
        30,
        sleep=lambda _s: None,
        clock=lambda: 0,
    )
    assert toks["access_token"] == "AT"


def test_poll_token_hard_error(env, patched_client):
    import pytest

    from nimctl import oidc
    from nimctl.config import resolve_settings
    from nimctl.errors import ConfigError

    fake = patched_client()
    endpoint = "/auth/realms/r/protocol/openid-connect/token"
    fake.add("POST", endpoint, {"error": "access_denied", "error_description": "nope"}, status=400)
    with pytest.raises(ConfigError):
        oidc.poll_token(
            resolve_settings(),
            "https://nim.test" + endpoint,
            "D",
            "cliapp",
            1,
            30,
            sleep=lambda _s: None,
            clock=lambda: 0,
        )


def test_login_oidc_saves_token_and_context(env, patched_client, tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    fake = patched_client("https://nim.test")
    fake.add("GET", "/auth/realms/r/.well-known/openid-configuration", OIDC_META)
    fake.add(
        "POST",
        "/auth/realms/r/protocol/openid-connect/auth/device",
        {
            "device_code": "D",
            "user_code": "ABCD-EFGH",
            "verification_uri_complete": "https://kc.test/device?user_code=ABCD-EFGH",
            "interval": 1,
            "expires_in": 30,
        },
    )
    fake.add(
        "POST",
        "/auth/realms/r/protocol/openid-connect/token",
        {"access_token": "AT", "refresh_token": "RT"},
    )
    dest = tmp_path / "tok.jwt"
    rc = main(
        [
            "--context",
            "default",
            "login-oidc",
            "--issuer",
            "https://nim.test/auth/realms/r",
            "--client-id",
            "cliapp",
            "--out",
            str(dest),
        ]
    )
    assert rc == 0
    assert dest.read_text() == "AT"
    assert (dest.with_suffix(".refresh")).read_text() == "RT"
    import stat

    assert stat.S_IMODE(dest.stat().st_mode) == 0o600
    err = capsys.readouterr().err
    assert "ABCD-EFGH" in err
    # context now stored
    from nimctl.config import load_config

    ctx = load_config().contexts["default"]
    assert ctx.oidc_issuer == "https://nim.test/auth/realms/r"
    assert ctx.oidc_client_id == "cliapp"
    assert ctx.token_file == str(dest)


def test_refresh_uses_stored_refresh_token(env, patched_client, tmp_path, monkeypatch):
    from nimctl.config import AppConfig, ContextConfig, save_config

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    tok = tmp_path / "tok.jwt"
    tok.write_text("OLD")
    (tmp_path / "tok.refresh").write_text("RT")
    save_config(
        AppConfig(
            current_context="default",
            contexts={
                "default": ContextConfig(
                    host="https://nim.test",
                    token_file=str(tok),
                    oidc_issuer="https://nim.test/auth/realms/r",
                    oidc_client_id="cliapp",
                )
            },
        )
    )
    fake = patched_client()
    fake.add("GET", "/auth/realms/r/.well-known/openid-configuration", OIDC_META)
    fake.add(
        "POST",
        "/auth/realms/r/protocol/openid-connect/token",
        {"access_token": "NEW", "refresh_token": "RT2"},
    )
    assert main(["refresh"]) == 0
    assert tok.read_text() == "NEW"
