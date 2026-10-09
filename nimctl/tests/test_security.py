from __future__ import annotations

from nimctl.cli import main


def run(*argv):
    return main(list(argv))


def test_security_support(env, patched_client, capsys):
    fake = patched_client()
    fake.add(
        "GET",
        "/api/platform/v1/analytics/security/support/123",
        {"items": [{"support_id": "123", "policy_name": "p"}]},
    )
    assert run("security", "support", "123") == 0
    assert "123" in capsys.readouterr().out


def test_security_events_builds_filter(env, patched_client):
    fake = patched_client()
    fake.add("GET", "/api/platform/v1/analytics/security/events", {"items": []})
    assert (
        run("security", "events", "--support-id", "123", "--policy", "p", "--page-size", "10") == 0
    )
    params = fake.calls[-1].url.params
    assert params["filter"] == "support_id=123 AND policy_name=p"
    assert params["pageSize"] == "10"


def test_security_events_by_id(env, patched_client, capsys):
    fake = patched_client()
    fake.add(
        "GET",
        "/api/platform/v1/analytics/security/events/abc",
        {"id": "abc", "support_id": "123"},
    )
    assert run("security", "events", "--id", "abc") == 0
    assert "abc" in capsys.readouterr().out


def test_security_events_no_filter_omits_param(env, patched_client):
    fake = patched_client()
    fake.add("GET", "/api/platform/v1/analytics/security/events", {"items": []})
    assert run("security", "events") == 0
    assert "filter" not in fake.calls[-1].url.params


def test_api_call_query_option(env, patched_client):
    fake = patched_client()
    fake.add("GET", "/api/platform/v1/analytics/security/events", {"items": []})
    assert (
        run(
            "api",
            "call",
            "GET",
            "/analytics/security/events",
            "-q",
            "filter=support_id=123",
            "-q",
            "pageSize=5",
        )
        == 0
    )
    params = fake.calls[-1].url.params
    assert params["filter"] == "support_id=123"
    assert params["pageSize"] == "5"


def test_api_call_query_rejects_bad_pair(env, patched_client, capsys):
    patched_client()
    assert run("api", "call", "GET", "/systems", "-q", "nope") == 2
    assert "expected key=value" in capsys.readouterr().err
