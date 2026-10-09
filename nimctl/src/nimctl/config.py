from __future__ import annotations

import os
import re
import tomllib
from contextvars import ContextVar
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

import tomli_w

from .errors import ConfigError, UsageError

_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_OUTPUT_MODES = {"json", "raw", "table"}
_BOOL_VALUES = {"true": True, "false": False, "1": True, "0": False, "yes": True, "no": False}


@dataclass
class GlobalOptions:
    context: str | None = None
    host: str | None = None
    api_version: str | None = None
    user: str | None = None
    password_file: Path | None = None
    token_file: Path | None = None
    trust: Path | None = None
    insecure: bool | None = None
    output: str | None = None
    quiet: bool = False
    refresh: bool = False


_GLOBALS: ContextVar[GlobalOptions | None] = ContextVar("nimctl_globals", default=None)


def get_globals() -> GlobalOptions:
    return _GLOBALS.get() or GlobalOptions()


def set_globals(options: GlobalOptions) -> None:
    _GLOBALS.set(options)


@dataclass
class ContextConfig:
    host: str | None = None
    api_version: str | None = None
    user: str | None = None
    password_file: str | None = None
    token_file: str | None = None
    trust: str | None = None
    oidc_issuer: str | None = None
    oidc_client_id: str | None = None
    insecure: bool = False


@dataclass
class AppConfig:
    current_context: str | None = None
    contexts: dict[str, ContextConfig] = field(default_factory=dict)


@dataclass
class Settings:
    host: str
    api_version: str
    user: str | None
    password: str | None
    token: str | None
    trust: str | None
    oidc_issuer: str | None
    oidc_client_id: str | None
    insecure: bool
    output: str
    quiet: bool
    refresh: bool
    spec_ttl: int
    timeout: float


def config_path() -> Path:
    base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "nimctl" / "config.toml"


def validate_context_name(name: str) -> None:
    if name == "nimctl" or not _NAME_RE.match(name):
        raise UsageError(f"invalid context name: {name!r}")


def load_config() -> AppConfig:
    path = config_path()
    if not path.exists():
        return AppConfig()
    data = tomllib.loads(path.read_text())
    allowed = {item.name for item in fields(ContextConfig)}
    contexts = {
        name: ContextConfig(**{key: value for key, value in values.items() if key in allowed})
        for name, values in data.get("contexts", {}).items()
    }
    current = data.get("nimctl", {}).get("current_context")
    return AppConfig(current_context=current, contexts=contexts)


def save_config(cfg: AppConfig) -> None:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, object] = {"contexts": {}}
    if cfg.current_context:
        payload["nimctl"] = {"current_context": cfg.current_context}
    payload["contexts"] = {
        name: {key: value for key, value in asdict(context).items() if value not in (None, False)}
        for name, context in cfg.contexts.items()
    }
    tmp = path.with_suffix(".tmp")
    tmp.write_text(tomli_w.dumps(payload))
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)


def current_context() -> str | None:
    return load_config().current_context


def active_context_name() -> str:
    chosen = get_globals().context or os.environ.get("NIMCTL_CONTEXT") or current_context()
    return chosen or "default"


def _read_secret(path: Path | None) -> str | None:
    if path is None or not path.exists():
        return None
    return path.read_text().strip()


def _env_bool(name: str) -> bool:
    return os.environ.get(name, "").lower() in {"1", "true", "yes", "on"}


def resolve_settings() -> Settings:
    g = get_globals()
    cfg = load_config()
    name = active_context_name()
    stored = cfg.contexts.get(name, ContextConfig())
    host = g.host or os.environ.get("NIMCTL_HOST") or stored.host
    api_version = (
        g.api_version or os.environ.get("NIMCTL_API_VERSION") or stored.api_version or "v1"
    )
    user = g.user or os.environ.get("NIMCTL_USER") or stored.user
    if g.password_file is not None:
        password = _read_secret(g.password_file)
    else:
        password = os.environ.get("NIMCTL_PASSWORD") or _read_secret(
            Path(stored.password_file) if stored.password_file else None
        )
    if g.token_file is not None:
        token = _read_secret(g.token_file)
    else:
        token = os.environ.get("NIMCTL_TOKEN") or _read_secret(
            Path(stored.token_file) if stored.token_file else None
        )
    if g.insecure is not None:
        insecure = g.insecure
    else:
        insecure = _env_bool("NIMCTL_INSECURE") or stored.insecure
    if g.trust is not None:
        trust: str | None = str(g.trust)
    else:
        trust = os.environ.get("NIMCTL_TRUST") or stored.trust
    oidc_issuer = os.environ.get("NIMCTL_OIDC_ISSUER") or stored.oidc_issuer
    oidc_client_id = os.environ.get("NIMCTL_OIDC_CLIENT_ID") or stored.oidc_client_id
    if not host:
        raise ConfigError("no host set; run 'nimctl context set host <url>' or pass --host")
    output = g.output or os.environ.get("NIMCTL_OUTPUT") or "json"
    if output not in _OUTPUT_MODES:
        raise UsageError(f"invalid output mode: {output!r} (choose json, raw or table)")
    return Settings(
        host=host.rstrip("/"),
        api_version=api_version,
        user=user,
        password=password,
        token=token,
        trust=trust,
        oidc_issuer=oidc_issuer,
        oidc_client_id=oidc_client_id,
        insecure=insecure,
        output=output,
        quiet=g.quiet or _env_bool("NIMCTL_QUIET"),
        refresh=g.refresh,
        spec_ttl=int(os.environ.get("NIMCTL_SPEC_TTL", "86400")),
        timeout=float(os.environ.get("NIMCTL_TIMEOUT", "30")),
    )
