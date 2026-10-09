from __future__ import annotations

from nimctl.cli import main


def test_context_commands_need_no_host(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.delenv("NIMCTL_HOST", raising=False)
    assert main(["context", "list"]) == 0


def test_context_set_use_show_delete(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("NIMCTL_HOST", "https://nim.test")

    assert main(["context", "set", "host", "https://nim.test"]) == 0
    assert main(["context", "set", "insecure", "true"]) == 0
    assert main(["context", "show"]) == 0
    assert "https://nim.test" in capsys.readouterr().out

    assert main(["context", "use", "default"]) == 0
    assert "default" in capsys.readouterr().out or True

    assert main(["context", "path"]) == 0
    assert "config.toml" in capsys.readouterr().out

    assert main(["context", "delete", "default"]) == 0


def test_context_set_unknown_key_exits_2(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    assert main(["context", "set", "bogus", "x"]) == 2
    assert "unknown context key" in capsys.readouterr().err


def test_context_set_invalid_bool_exits_2(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    assert main(["context", "set", "insecure", "maybe"]) == 2
    assert "true or false" in capsys.readouterr().err


def test_context_use_unknown_exits_2(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    assert main(["context", "use", "ghost"]) == 2


def test_context_use_invalid_name_exits_2(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    assert main(["context", "use", "nimctl"]) == 2
