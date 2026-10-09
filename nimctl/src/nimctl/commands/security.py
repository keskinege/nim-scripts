from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path

import typer

from .. import http
from ..config import Settings, resolve_settings
from ..errors import ConfigError
from ..render import render

app = typer.Typer(
    no_args_is_help=True, help="App Protect security: events, policies, log profiles."
)


def _build_filter(support_id: str | None, policy: str | None, extra: str | None) -> str | None:
    parts = []
    if support_id:
        parts.append(f"support_id={support_id}")
    if policy:
        parts.append(f"policy_name={policy}")
    if extra:
        parts.append(extra)
    return " AND ".join(parts) if parts else None


@app.command("support")
def support(support_id: str) -> None:
    """List the security events recorded for one support ID."""
    settings = resolve_settings()
    render(
        http.request_json(settings, "GET", f"/analytics/security/support/{support_id}"),
        mode=settings.output,
    )


@app.command("events")
def events(
    support_id: str | None = typer.Option(None, "--support-id", help="Filter by support ID."),
    policy: str | None = typer.Option(None, "--policy", help="Filter by policy name."),
    filter_: str | None = typer.Option(None, "--filter", help="Raw filter expression."),
    start_time: str | None = typer.Option(None, "--start-time"),
    end_time: str | None = typer.Option(None, "--end-time"),
    page_size: int | None = typer.Option(None, "--page-size", min=0, max=100),
    include_total: bool = typer.Option(False, "--include-total"),
    event_id: str | None = typer.Option(None, "--id", help="Fetch a single event by its UUID."),
) -> None:
    """Search security events, or fetch one event with --id."""
    settings = resolve_settings()
    if event_id:
        render(
            http.request_json(settings, "GET", f"/analytics/security/events/{event_id}"),
            mode=settings.output,
        )
        return
    params: dict[str, str] = {}
    combined = _build_filter(support_id, policy, filter_)
    if combined:
        params["filter"] = combined
    if start_time:
        params["startTime"] = start_time
    if end_time:
        params["endTime"] = end_time
    if page_size is not None:
        params["pageSize"] = str(page_size)
    if include_total:
        params["includeTotal"] = "true"
    render(
        http.request_json(settings, "GET", "/analytics/security/events", params=params or None),
        mode=settings.output,
    )


# --- policies ---------------------------------------------------------------

policies_app = typer.Typer(no_args_is_help=True, help="Manage App Protect security policies.")


def _b64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode()


def _safe(name: str) -> str:
    keep = "-_."
    return "".join(c if c.isalnum() or c in keep else "_" for c in name).strip("._") or "unnamed"


@policies_app.command("list")
def policies_list(
    include_content: bool = typer.Option(
        False, "--include-content", help="Include base64 content."
    ),
    versions: str | None = typer.Option(None, "--versions"),
) -> None:
    settings = resolve_settings()
    params: dict[str, str] = {}
    if include_content:
        params["includePolicyContent"] = "true"
    if versions:
        params["versions"] = versions
    render(
        http.request_json(settings, "GET", "/security/policies", params=params or None),
        mode=settings.output,
    )


@policies_app.command("get")
def policies_get(
    security_policy_uid: str,
    decode: bool = typer.Option(False, "--decode", help="Print the decoded policy JSON."),
) -> None:
    settings = resolve_settings()
    data = http.request_json(settings, "GET", f"/security/policies/{security_policy_uid}")
    if decode:
        content = (data or {}).get("content")
        typer.echo(base64.b64decode(content).decode() if content else "")
        return
    render(data, mode=settings.output)


@policies_app.command("create")
def policies_create(
    name: str = typer.Option(..., "--name", help="Unique policy name (metadata.name)."),
    file: Path = typer.Option(
        ..., "--file", exists=True, dir_okay=False, help="App Protect policy JSON file."
    ),
    display_name: str | None = typer.Option(None, "--display-name"),
    description: str | None = typer.Option(None, "--description"),
    openapi: Path | None = typer.Option(None, "--openapi", exists=True, dir_okay=False),
    update: bool = typer.Option(False, "--update", help="PUT (new version) instead of POST."),
) -> None:
    """Create (or update) a NIM security policy from a local policy JSON file."""
    settings = resolve_settings()
    metadata: dict[str, str] = {"name": name}
    if display_name:
        metadata["displayName"] = display_name
    if description:
        metadata["description"] = description
    body: dict[str, object] = {"metadata": metadata, "content": _b64(file)}
    if openapi:
        body["openAPISpecContent"] = _b64(openapi)
    url = f"/security/policies/{name}" if update else "/security/policies"
    method = "PUT" if update else "POST"
    render(http.request_json(settings, method, url, json_body=body), mode=settings.output)


@policies_app.command("delete")
def policies_delete(security_policy_uid: str) -> None:
    settings = resolve_settings()
    http.request(settings, "DELETE", f"/security/policies/{security_policy_uid}")


@policies_app.command("bundles")
def policies_bundles() -> None:
    settings = resolve_settings()
    render(http.request_json(settings, "GET", "/security/policies/bundles"), mode=settings.output)


def _verify(data: bytes, size: int | None, sha256: str | None) -> None:
    if size is not None and len(data) != size:
        raise ConfigError(f"bundle size mismatch: expected {size}, got {len(data)}")
    if sha256 is not None and hashlib.sha256(data).hexdigest() != sha256:
        raise ConfigError("bundle hash mismatch")


def _download_bundles(settings: Settings, out: Path, uid: str | None) -> list[Path]:
    items = (http.request_json(settings, "GET", "/security/policies/bundles") or {}).get(
        "items", []
    )
    out.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for item in items:
        meta = item.get("metadata", {})
        if uid and meta.get("uid") != uid:
            continue
        resp = http.request_json(
            settings, "GET", f"/security/policies/{meta['policyUID']}/bundles/{meta['uid']}"
        )
        raw = base64.b64decode((resp or {}).get("content") or "")
        _verify(raw, meta.get("size"), meta.get("hash"))
        stem = f"{_safe(meta['policyName'])}.{meta['uid'][:8]}"
        ext = ".tgz" if raw[:2] == b"\x1f\x8b" else ".bundle"
        (out / (stem + ext)).write_bytes(raw)
        (out / (stem + ".json")).write_text(json.dumps(item, indent=2))
        written.append(out / (stem + ext))
    return written


@policies_app.command("download")
def policies_download(
    out: Path = typer.Option(Path("bundles"), "--out", dir_okay=True),
    uid: str | None = typer.Option(None, "--uid", help="Only this bundle UID."),
) -> None:
    """Download compiled policy bundles (hash-verified) plus a metadata sidecar."""
    settings = resolve_settings()
    for path in _download_bundles(settings, out, uid):
        typer.echo(str(path), err=True)


app.add_typer(policies_app, name="policies")


# --- log profiles -----------------------------------------------------------

logprofiles_app = typer.Typer(no_args_is_help=True, help="Manage App Protect log profiles.")


@logprofiles_app.command("list")
def logprofiles_list() -> None:
    settings = resolve_settings()
    render(http.request_json(settings, "GET", "/security/logprofiles"), mode=settings.output)


@logprofiles_app.command("get")
def logprofiles_get(log_profile_name: str) -> None:
    settings = resolve_settings()
    render(
        http.request_json(settings, "GET", f"/security/logprofiles/{log_profile_name}"),
        mode=settings.output,
    )


@logprofiles_app.command("create")
def logprofiles_create(
    name: str = typer.Option(..., "--name"),
    file: Path = typer.Option(..., "--file", exists=True, dir_okay=False),
    update: bool = typer.Option(False, "--update"),
) -> None:
    settings = resolve_settings()
    body = {"metadata": {"name": name}, "logProfileContent": _b64(file)}
    url = f"/security/logprofiles/{name}" if update else "/security/logprofiles"
    method = "PUT" if update else "POST"
    render(http.request_json(settings, method, url, json_body=body), mode=settings.output)


@logprofiles_app.command("delete")
def logprofiles_delete(log_profile_name: str) -> None:
    settings = resolve_settings()
    http.request(settings, "DELETE", f"/security/logprofiles/{log_profile_name}")


app.add_typer(logprofiles_app, name="log-profiles")


# --- compiler ---------------------------------------------------------------

compiler_app = typer.Typer(no_args_is_help=True, help="App Protect compiler versions.")


@compiler_app.command("versions")
def compiler_versions(latest: bool = typer.Option(False, "--latest")) -> None:
    settings = resolve_settings()
    path = "/security/nap-compiler/versions/latest" if latest else "/security/nap-compiler/versions"
    render(http.request_json(settings, "GET", path), mode=settings.output)


app.add_typer(compiler_app, name="compiler")
