from __future__ import annotations

import base64
import gzip
import hashlib
import json

from nimctl.cli import main


def run(*argv):
    return main(list(argv))


def _b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode()


# --- security policies ------------------------------------------------------


def test_policies_list_can_include_content(env, patched_client):
    fake = patched_client()
    fake.add("GET", "/api/platform/v1/security/policies", {"items": []})
    assert run("security", "policies", "list", "--include-content") == 0
    assert fake.calls[-1].url.params["includePolicyContent"] == "true"


def test_policies_get_decode(env, patched_client, capsys):
    fake = patched_client()
    raw = json.dumps({"policy": {"name": "demo"}})
    fake.add("GET", "/api/platform/v1/security/policies/u1", {"content": _b64(raw.encode())})
    assert run("security", "policies", "get", "u1", "--decode") == 0
    assert json.loads(capsys.readouterr().out) == {"policy": {"name": "demo"}}


def test_policies_create_wraps_json_as_base64(env, patched_client, tmp_path):
    src = tmp_path / "policy.json"
    src.write_text(json.dumps({"policy": {"name": "demo", "enforcementMode": "blocking"}}))
    fake = patched_client()
    fake.add("GET", "/api/platform/v1/security/nap-compiler/versions/latest", {})
    fake.add(
        "POST", "/api/platform/v1/security/policies", {"metadata": {"name": "demo"}}, status=201
    )
    assert run("security", "policies", "create", "--name", "demo", "--file", str(src)) == 0
    body = json.loads(fake.calls[-1].content)
    assert body["metadata"] == {"name": "demo"}
    assert json.loads(base64.b64decode(body["content"])) == {
        "policy": {"name": "demo", "enforcementMode": "blocking"}
    }


def test_policies_create_update_uses_put(env, patched_client, tmp_path):
    src = tmp_path / "policy.json"
    src.write_text("{}")
    fake = patched_client()
    fake.add("PUT", "/api/platform/v1/security/policies/demo", {"metadata": {}}, status=201)
    assert (
        run("security", "policies", "create", "--name", "demo", "--file", str(src), "--update") == 0
    )
    assert fake.calls[-1].method == "PUT"


def test_policies_download_writes_bundle_and_sidecar(env, patched_client, tmp_path):
    raw = gzip.compress(b"hello")
    digest = hashlib.sha256(raw).hexdigest()
    fake = patched_client()
    fake.add(
        "GET",
        "/api/platform/v1/security/policies/bundles",
        {
            "items": [
                {
                    "metadata": {
                        "policyName": "demo",
                        "policyUID": "p1",
                        "uid": "buid12345",
                        "size": len(raw),
                        "hash": digest,
                    }
                }
            ]
        },
    )
    fake.add(
        "GET", "/api/platform/v1/security/policies/p1/bundles/buid12345", {"content": _b64(raw)}
    )
    out = tmp_path / "out"
    assert run("security", "policies", "download", "--out", str(out)) == 0
    bundle = out / "demo.buid1234.tgz"
    assert bundle.read_bytes() == raw
    assert (out / "demo.buid1234.json").exists()


def test_policies_download_detects_non_gzip(env, patched_client, tmp_path):
    raw = b"not a gzip file"
    fake = patched_client()
    fake.add(
        "GET",
        "/api/platform/v1/security/policies/bundles",
        {"items": [{"metadata": {"policyName": "d", "policyUID": "p1", "uid": "u1234567"}}]},
    )
    fake.add(
        "GET", "/api/platform/v1/security/policies/p1/bundles/u1234567", {"content": _b64(raw)}
    )
    out = tmp_path / "out"
    assert run("security", "policies", "download", "--out", str(out)) == 0
    assert (out / "d.u1234567.bundle").read_bytes() == raw


def test_policies_download_hash_mismatch_exits_1(env, patched_client, tmp_path, capsys):
    raw = b"data"
    fake = patched_client()
    fake.add(
        "GET",
        "/api/platform/v1/security/policies/bundles",
        {
            "items": [
                {
                    "metadata": {
                        "policyName": "d",
                        "policyUID": "p1",
                        "uid": "u1234567",
                        "hash": "deadbeef",
                    }
                }
            ]
        },
    )
    fake.add(
        "GET", "/api/platform/v1/security/policies/p1/bundles/u1234567", {"content": _b64(raw)}
    )
    assert run("security", "policies", "download", "--out", str(tmp_path / "out")) == 1
    assert "hash mismatch" in capsys.readouterr().err


# --- log profiles / compiler ------------------------------------------------


def test_logprofiles_list(env, patched_client, capsys):
    fake = patched_client()
    fake.add("GET", "/api/platform/v1/security/logprofiles", {"items": []})
    assert run("security", "log-profiles", "list") == 0


def test_compiler_versions_latest(env, patched_client):
    fake = patched_client()
    fake.add("GET", "/api/platform/v1/security/nap-compiler/versions/latest", {"version": "5.0"})
    assert run("security", "compiler", "versions", "--latest") == 0
    assert fake.calls[-1].url.path.endswith("/versions/latest")


# --- tier 1 -----------------------------------------------------------------


def test_certs_list_pagination(env, patched_client):
    fake = patched_client()
    fake.add("GET", "/api/platform/v1/certs", {"items": []})
    assert run("certs", "list", "--limit", "10") == 0
    assert fake.calls[-1].url.params["limit"] == "10"


def test_certs_summary(env, patched_client):
    fake = patched_client()
    fake.add("GET", "/api/platform/v1/certs/summary", {"count": 0})
    assert run("certs", "summary") == 0


def test_instance_groups_list(env, patched_client):
    fake = patched_client()
    fake.add("GET", "/api/platform/v1/instance-groups", {"items": []})
    assert run("instance-groups", "list") == 0


def test_instance_groups_deployment(env, patched_client, capsys):
    fake = patched_client()
    fake.add("GET", "/api/platform/v1/instance-groups/deployments/d1", {"id": "d1"})
    assert run("instance-groups", "deployment", "d1") == 0
    assert "d1" in capsys.readouterr().out


def test_usage_records_params(env, patched_client):
    fake = patched_client()
    fake.add("GET", "/api/platform/v1/usage-records", {"items": []})
    assert run("usage", "records", "--nginx-uid", "ngx-1", "--limit", "5") == 0
    params = fake.calls[-1].url.params
    assert params["nginxUid"] == "ngx-1" and params["limit"] == "5"


def test_usage_export_prints_csv(env, patched_client, capsys):
    fake = patched_client()
    fake.add("GET", "/api/platform/v1/usage-records/export", "a,b\n1,2\n")
    assert run("usage", "export") == 0
    assert "a,b" in capsys.readouterr().out


def test_events_list_params(env, patched_client):
    fake = patched_client()
    fake.add("GET", "/api/platform/v1/analytics/events", {"items": []})
    assert run("events", "list", "--filter", "type=deploy", "--page-size", "10") == 0
    params = fake.calls[-1].url.params
    assert params["filter"] == "type=deploy" and params["pageSize"] == "10"


def test_platform_config_show(env, patched_client):
    fake = patched_client()
    fake.add("GET", "/api/platform/v1/platform-config/settings", {"value": 1})
    assert run("platform-config", "show", "settings") == 0


def test_staged_configs_list(env, patched_client):
    fake = patched_client()
    fake.add("GET", "/api/platform/v1/configs", {"items": []})
    assert run("staged-configs", "list") == 0


# --- tier 3 -----------------------------------------------------------------


def test_users_list_gets_rendered(env, patched_client, capsys):
    fake = patched_client()
    fake.add("GET", "/api/platform/v1/users", {"items": [{"name": "admin"}]})
    assert run("users", "list") == 0
    assert "admin" in capsys.readouterr().out


def test_users_create_posts_body(env, patched_client, tmp_path):
    body = tmp_path / "u.json"
    body.write_text(json.dumps({"username": "bob"}))
    fake = patched_client()
    fake.add("POST", "/api/platform/v1/users", {"username": "bob"}, status=201)
    assert run("users", "create", "--body", str(body)) == 0
    assert json.loads(fake.calls[-1].content) == {"username": "bob"}


def test_roles_features(env, patched_client):
    fake = patched_client()
    fake.add("GET", "/api/platform/v1/features", {"items": []})
    assert run("roles", "features") == 0


def test_groups_list_filter(env, patched_client):
    fake = patched_client()
    fake.add("GET", "/api/platform/v1/groups", {"items": []})
    assert run("groups", "list", "--filter", "admins") == 0
    assert fake.calls[-1].url.params["groupNameFilter"] == "admins"


def test_resource_groups_list(env, patched_client):
    fake = patched_client()
    fake.add("GET", "/api/platform/v1/resource-groups", {"items": []})
    assert run("resource-groups", "list", "--show-details") == 0
    assert fake.calls[-1].url.params["showDetails"] == "true"
