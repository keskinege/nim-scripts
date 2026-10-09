from __future__ import annotations

import json
from pathlib import Path

from nimctl.cli import main

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str):
    return json.loads((FIXTURES / name).read_text())


def run(*argv):
    return main(list(argv))


def test_systems_list(env, patched_client, capsys):
    fake = patched_client()
    fake.add("GET", "/api/platform/v1/systems", load_fixture("systems.json"))
    assert run("systems", "list") == 0
    assert "nginx-01" in capsys.readouterr().out


def test_systems_get(env, patched_client, capsys):
    fake = patched_client()
    fake.add("GET", "/api/platform/v1/systems/sys-1", {"uid": "sys-1", "hostname": "nginx-01"})
    assert run("systems", "get", "sys-1") == 0
    assert "sys-1" in capsys.readouterr().out


def test_systems_delete_is_204(env, patched_client):
    fake = patched_client()
    fake.add("DELETE", "/api/platform/v1/systems/sys-1", None, status=204)
    assert run("systems", "delete", "sys-1") == 0


def test_instances_list(env, patched_client, capsys):
    fake = patched_client()
    fake.add("GET", "/api/platform/v1/instances", load_fixture("instances.json"))
    assert run("instances", "list") == 0
    assert "nginx-01" in capsys.readouterr().out


def test_instances_list_by_system(env, patched_client, capsys):
    fake = patched_client()
    fake.add(
        "GET",
        "/api/platform/v1/systems/sys-1/instances",
        {"items": [{"uid": "ngx-1", "displayName": "nginx-01"}]},
    )
    assert run("instances", "list-by-system", "sys-1") == 0


def test_configs_get_decode(env, patched_client, capsys):
    fake = patched_client()
    fake.add(
        "GET", "/api/platform/v1/systems/sys-1/instances/ngx-1/config", load_fixture("config.json")
    )
    assert (
        run("configs", "get", "sys-1", "ngx-1", "--decode", "/etc/nginx/conf.d/default.conf") == 0
    )
    assert "server { listen 80; }" in capsys.readouterr().out


def test_configs_get_decode_missing_file_exits_1(env, patched_client, capsys):
    fake = patched_client()
    fake.add(
        "GET", "/api/platform/v1/systems/sys-1/instances/ngx-1/config", load_fixture("config.json")
    )
    assert run("configs", "get", "sys-1", "ngx-1", "--decode", "/nope.conf") == 1
    assert "config file not found" in capsys.readouterr().err


def test_configs_publish(env, patched_client, tmp_path, capsys):
    body = tmp_path / "pub.json"
    body.write_text(json.dumps({"configFiles": []}))
    fake = patched_client()
    fake.add(
        "POST",
        "/api/platform/v1/systems/sys-1/instances/ngx-1/config",
        {"deploymentUID": "dep-1", "result": "success", "links": {}},
        status=202,
    )
    assert run("configs", "publish", "sys-1", "ngx-1", "--body", str(body)) == 0


def test_configs_publish_wait_polls_until_successful(env, patched_client, tmp_path, monkeypatch):
    monkeypatch.setenv("NIMCTL_POLL_INTERVAL", "0")
    body = tmp_path / "pub.json"
    body.write_text(json.dumps({"configFiles": []}))
    fake = patched_client()
    fake.add(
        "POST",
        "/api/platform/v1/systems/sys-1/instances/ngx-1/config",
        {"deploymentUID": "dep-1", "result": "success", "links": {}},
        status=202,
    )
    fake.add_sequence(
        "GET",
        "/api/platform/v1/systems/instances/deployments/dep-1",
        [
            (200, {"id": "dep-1", "status": "pending"}),
            (200, {"id": "dep-1", "status": "successful"}),
        ],
    )
    assert (
        run(
            "configs",
            "publish",
            "sys-1",
            "ngx-1",
            "--body",
            str(body),
            "--wait",
            "--output",
            "json",
        )
        == 0
    )


def test_configs_publish_wait_failed_exits_1(env, patched_client, tmp_path, monkeypatch):
    monkeypatch.setenv("NIMCTL_POLL_INTERVAL", "0")
    body = tmp_path / "pub.json"
    body.write_text(json.dumps({"configFiles": []}))
    fake = patched_client()
    fake.add(
        "POST",
        "/api/platform/v1/systems/sys-1/instances/ngx-1/config",
        {"deploymentUID": "dep-1", "result": "success", "links": {}},
        status=202,
    )
    fake.add(
        "GET",
        "/api/platform/v1/systems/instances/deployments/dep-1",
        {"id": "dep-1", "status": "failed"},
    )
    assert run("configs", "publish", "sys-1", "ngx-1", "--body", str(body), "--wait") == 1


def test_configs_publish_wait_polls_deployment_uid(env, patched_client, tmp_path, monkeypatch):
    # Regression: NIM returns deploymentUID (not "id"); --wait must poll it.
    monkeypatch.setenv("NIMCTL_POLL_INTERVAL", "0")
    body = tmp_path / "pub.json"
    body.write_text(json.dumps({"configFiles": []}))
    fake = patched_client()
    fake.add(
        "POST",
        "/api/platform/v1/systems/sys-1/instances/ngx-1/config",
        {"deploymentUID": "dep-9", "result": "success", "links": {}},
        status=202,
    )
    fake.add(
        "GET",
        "/api/platform/v1/systems/instances/deployments/dep-9",
        {"id": "dep-9", "status": "successful"},
    )
    assert run("configs", "publish", "sys-1", "ngx-1", "--body", str(body), "--wait") == 0
    assert any(c.url.path.endswith("/deployments/dep-9") for c in fake.calls)


def test_configs_deployment(env, patched_client, capsys):
    fake = patched_client()
    fake.add(
        "GET",
        "/api/platform/v1/systems/instances/deployments/dep-1",
        load_fixture("deployment.json"),
    )
    assert run("configs", "deployment", "dep-1") == 0
    assert "dep-1" in capsys.readouterr().out


def test_scan_start(env, patched_client, capsys):
    fake = patched_client()
    fake.add("POST", "/api/platform/v1/servers/scan", {"status": "scanning"}, status=202)
    assert run("scan", "start", "10.0.0.0/24") == 0


def test_scan_start_wait(env, patched_client, monkeypatch):
    monkeypatch.setenv("NIMCTL_POLL_INTERVAL", "0")
    fake = patched_client()
    fake.add("POST", "/api/platform/v1/servers/scan", {"status": "scanning"}, status=202)
    fake.add_sequence(
        "GET",
        "/api/platform/v1/servers/scan",
        [(200, {"status": "scanning"}), (200, {"status": "complete"})],
    )
    assert run("scan", "start", "10.0.0.0/24", "--wait") == 0


def test_scan_cancel(env, patched_client):
    fake = patched_client()
    fake.add("DELETE", "/api/platform/v1/servers/scan", None, status=204)
    assert run("scan", "cancel") == 0


def test_metrics_query_sends_params(env, patched_client):
    fake = patched_client()
    fake.add("GET", "/api/platform/v1/analytics/metrics", {"items": []})
    assert (
        run(
            "metrics",
            "query",
            "--names",
            "nginx.http.request.count",
            "--start-time",
            "2026-01-01",
            "--resolution",
            "1m",
        )
        == 0
    )
    params = fake.calls[-1].url.params
    assert params["names"] == "nginx.http.request.count"
    assert params["startTime"] == "2026-01-01"


def test_catalogs_show(env, patched_client):
    fake = patched_client()
    fake.add(
        "GET", "/api/platform/v1/analytics/catalogs/metrics", load_fixture("catalogs_metrics.json")
    )
    assert run("catalogs", "show", "metrics") == 0


def test_catalogs_bad_kind_exits_2(env, capsys):
    assert run("catalogs", "show", "widgets") == 2


def test_platform_health(env, patched_client, capsys):
    fake = patched_client()
    fake.add("GET", "/api/platform/v1/health", load_fixture("health.json"))
    assert run("health") == 0
    assert "healthy" in capsys.readouterr().out


def test_platform_modules_licensed(env, patched_client):
    fake = patched_client()
    fake.add("GET", "/api/platform/v1/modules/licensed", load_fixture("modules.json"))
    assert run("modules", "--licensed") == 0


def test_platform_license_status(env, patched_client, capsys):
    fake = patched_client()
    fake.add("GET", "/api/platform/v1/license/status", load_fixture("license_status.json"))
    assert run("license", "--status") == 0
    assert "VALID" in capsys.readouterr().out


def test_platform_version_falls_back_when_unavailable(env, patched_client, capsys):
    fake = patched_client()
    fake.add("GET", "/api/platform/v1/versions", {"message": "nope"}, status=404)
    assert run("version") == 0
    assert "api_version=v1" in capsys.readouterr().out


def test_auth_whoami(env, patched_client, capsys):
    fake = patched_client()
    fake.add("GET", "/api/platform/v1/userinfo", load_fixture("userinfo.json"))
    assert run("whoami") == 0
    assert "admin" in capsys.readouterr().out


def test_api_call_passthrough(env, patched_client, tmp_path):
    body = tmp_path / "body.json"
    body.write_text(json.dumps({"hostname": "x"}))
    fake = patched_client()
    fake.add("POST", "/api/platform/v1/systems", {"uid": "sys-1"}, status=201)
    assert run("api", "call", "POST", "/systems", "--body", str(body)) == 0
    assert json.loads(fake.calls[-1].content) == {"hostname": "x"}


def test_api_tags(env, patched_client, capsys):
    fake = patched_client()
    fake.add(
        "GET",
        "/ui/manager.json",
        {
            "paths": {
                "/systems": {"get": {"tags": ["systems"]}},
                "/health": {"get": {"tags": ["Health"]}},
            }
        },
    )
    assert run("api", "tags") == 0
    out = capsys.readouterr().out
    assert "systems" in out and "Health" in out
