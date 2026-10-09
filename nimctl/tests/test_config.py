from __future__ import annotations

import stat

import pytest

from nimctl.config import (
    ContextConfig,
    GlobalOptions,
    active_context_name,
    config_path,
    load_config,
    resolve_settings,
    save_config,
    set_globals,
    validate_context_name,
)
from nimctl.errors import ConfigError, UsageError


@pytest.mark.parametrize("name", ["default", "prod-1", "a.b_c", "A1"])
def test_validate_context_name_accepts(name):
    validate_context_name(name)


@pytest.mark.parametrize("name", ["nimctl", "", "-bad", "has space", "1x/"])
def test_validate_context_name_rejects(name):
    with pytest.raises(UsageError):
        validate_context_name(name)


def test_resolution_prefers_flag_over_env_and_store(env, monkeypatch):
    monkeypatch.setenv("NIMCTL_CONTEXT", "default")
    monkeypatch.setenv("NIMCTL_HOST", "https://env.example.ts.net")
    save_config(config_store(host="https://store.example.ts.net"))
    set_globals(GlobalOptions(host="https://flag.example.ts.net"))
    assert resolve_settings().host == "https://flag.example.ts.net"


def test_env_used_when_no_flag(env, monkeypatch):
    monkeypatch.setenv("NIMCTL_HOST", "https://env.example.ts.net")
    assert resolve_settings().host == "https://env.example.ts.net"


def test_stored_value_used_when_no_flag_or_env(env, monkeypatch):
    monkeypatch.delenv("NIMCTL_HOST", raising=False)
    save_config(config_store(host="https://store.example.ts.net"))
    assert resolve_settings().host == "https://store.example.ts.net"


def test_host_trailing_slash_is_stripped(env, monkeypatch):
    monkeypatch.setenv("NIMCTL_HOST", "https://nim.test/")
    assert resolve_settings().host == "https://nim.test"


def test_missing_host_raises_config_error(tmp_path, monkeypatch):
    monkeypatch.delenv("NIMCTL_HOST", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    with pytest.raises(ConfigError):
        resolve_settings()


def test_invalid_output_mode_raises_usage(env, monkeypatch):
    monkeypatch.setenv("NIMCTL_OUTPUT", "xml")
    with pytest.raises(UsageError):
        resolve_settings()


def test_api_version_defaults_to_v1(env):
    assert resolve_settings().api_version == "v1"


def test_insecure_reads_env(env, monkeypatch):
    monkeypatch.setenv("NIMCTL_INSECURE", "yes")
    assert resolve_settings().insecure is True


def test_password_and_token_from_files(env, monkeypatch, tmp_path):
    pw = tmp_path / "pw"
    pw.write_text("s3cret\n")
    tok = tmp_path / "tok"
    tok.write_text("eyJhbGci\n")
    set_globals(GlobalOptions(password_file=pw, token_file=tok))
    settings = resolve_settings()
    assert settings.password == "s3cret"
    assert settings.token == "eyJhbGci"


def test_config_roundtrip_and_permissions(env):
    cfg = config_store(host="https://nim.test")
    cfg.current_context = "default"
    save_config(cfg)
    loaded = load_config()
    assert loaded.current_context == "default"
    assert loaded.contexts["default"].host == "https://nim.test"
    mode = config_path().stat().st_mode
    assert stat.S_IMODE(mode) == 0o600


def test_active_context_name_prefers_flag(env, monkeypatch):
    monkeypatch.setenv("NIMCTL_CONTEXT", "env-ctx")
    set_globals(GlobalOptions(context="flag-ctx"))
    assert active_context_name() == "flag-ctx"


def test_active_context_name_defaults(env, monkeypatch):
    monkeypatch.delenv("NIMCTL_CONTEXT", raising=False)
    assert active_context_name() == "default"


def config_store(**ctx):
    from nimctl.config import AppConfig

    return AppConfig(current_context=None, contexts={"default": ContextConfig(**ctx)})
