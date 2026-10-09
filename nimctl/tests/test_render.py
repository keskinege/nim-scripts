from __future__ import annotations

import io

import pytest

from nimctl.errors import UsageError
from nimctl.render import render


def out():
    return io.StringIO()


def test_json_mode():
    buf = out()
    render({"a": 1}, mode="json", out=buf)
    assert buf.getvalue().strip() == '{\n  "a": 1\n}'


def test_raw_mode_with_string():
    buf = out()
    render("hello", mode="raw", out=buf)
    assert buf.getvalue() == "hello\n"


def test_raw_mode_with_object():
    buf = out()
    render({"a": 1}, mode="raw", out=buf)
    assert buf.getvalue() == '{"a": 1}\n'


def test_table_mode_uses_columns():
    buf = out()
    render(
        {"items": [{"hostname": "n1", "uid": "u1"}]},
        mode="table",
        columns=["hostname", "uid"],
        out=buf,
    )
    assert buf.getvalue() == "n1\tu1\n"


def test_table_mode_dotted_column():
    buf = out()
    render([{"metadata": {"name": "demo"}}], mode="table", columns=["metadata.name"], out=buf)
    assert buf.getvalue() == "demo\n"


def test_table_mode_missing_column_is_none():
    buf = out()
    render([{"uid": "u1"}], mode="table", columns=["hostname"], out=buf)
    assert buf.getvalue() == "None\n"


def test_table_mode_requires_columns():
    with pytest.raises(UsageError):
        render({"items": []}, mode="table", out=out())


def test_unknown_mode_raises():
    with pytest.raises(UsageError):
        render({}, mode="bogus", out=out())


def test_table_renders_bare_object_as_single_row():
    buf = out()
    render({"hostname": "solo"}, mode="table", columns=["hostname"], out=buf)
    assert buf.getvalue() == "solo\n"
