from __future__ import annotations

import pytest

from nimctl import http  # noqa: F401  (kept for symmetry with plan)
from nimctl.config import resolve_settings
from nimctl.pagination import paged_get


def test_limit_zero_is_accepted(env, patched_client):
    fake = patched_client()
    fake.add("GET", "/api/platform/v1/systems", {"count": 0, "items": []})
    paged_get(resolve_settings(), "/systems", limit=0)
    assert fake.calls[-1].url.params["limit"] == "0"


@pytest.mark.parametrize("limit", [-1, 101])
def test_limit_out_of_range(env, limit):
    from nimctl.errors import UsageError

    with pytest.raises(UsageError):
        paged_get(resolve_settings(), "/systems", limit=limit)


def test_negative_offset_is_usage_error(env):
    from nimctl.errors import UsageError

    with pytest.raises(UsageError):
        paged_get(resolve_settings(), "/systems", offset=-1)


def test_no_params_when_none(env, patched_client):
    fake = patched_client()
    fake.add("GET", "/api/platform/v1/systems", {"count": 0, "items": []})
    paged_get(resolve_settings(), "/systems")
    assert str(fake.calls[-1].url.params) == ""
