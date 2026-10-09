from __future__ import annotations

import json
from collections import deque
from pathlib import Path
from typing import Any

import httpx
import pytest

FIXTURES = Path(__file__).parent / "fixtures"


class FakeNIM:
    """Request-matched fake transport (per the implementation plan).

    Routes are keyed on ``(METHOD, url.path)`` with a per-route FIFO of queued
    responses. An unmatched request or an exhausted queue raises immediately, so
    a test can never silently pass because a request was never made.
    """

    def __init__(self) -> None:
        self.routes: dict[tuple[str, str], deque[tuple[int, Any]]] = {}
        self.calls: list[httpx.Request] = []

    def add(
        self,
        method: str,
        path: str,
        body: Any,
        status: int = 200,
        times: int = 1,
        headers: dict[str, str] | None = None,
    ) -> FakeNIM:
        queue = self.routes.setdefault((method.upper(), path), deque())
        for _ in range(times):
            queue.append((status, body, headers))
        return self

    def add_sequence(self, method: str, path: str, items: list) -> FakeNIM:
        queue = self.routes.setdefault((method.upper(), path), deque())
        for item in items:
            if len(item) == 2:
                status, body = item
                headers = None
            else:
                status, body, headers = item
            queue.append((status, body, headers))
        return self

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(request)
        key = (request.method.upper(), request.url.path)
        queue = self.routes.get(key)
        if queue is None:
            raise AssertionError(f"unexpected request: {key[0]} {key[1]}")
        if not queue:
            raise AssertionError(f"response queue exhausted for {key}")
        status, body, headers = queue.popleft()
        if body is None:
            return httpx.Response(status, headers=headers)
        if isinstance(body, (dict, list)):
            return httpx.Response(status, json=body, headers=headers)
        return httpx.Response(status, text=str(body), headers=headers)

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handler)


@pytest.fixture(autouse=True)
def _reset_globals():
    from nimctl.config import GlobalOptions, set_globals

    set_globals(GlobalOptions())
    yield
    set_globals(GlobalOptions())


@pytest.fixture
def fake() -> FakeNIM:
    return FakeNIM()


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("NIMCTL_HOST", "https://nim.test")
    monkeypatch.setenv("NIMCTL_PASSWORD", "x")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    return tmp_path


@pytest.fixture
def patched_client(fake, monkeypatch):
    # Inject the transport, not the factory: make_client still builds the real
    # client so headers/auth/verify/timeout are exercised, and MockTransport
    # delivers the fully-built request to the fake.
    def install(base_url: str = "https://nim.test") -> FakeNIM:
        monkeypatch.setattr("nimctl.http._TEST_TRANSPORT", fake.transport())
        return fake

    return install


def load_fixture(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text())


@pytest.fixture
def fixtures():
    return load_fixture
