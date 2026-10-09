from __future__ import annotations

from nimctl.cli import main


def test_version(capsys):
    assert main(["--version"]) == 0
    assert capsys.readouterr().out.strip() == "nimctl 0.5.0"


def test_help_lists_commands(capsys):
    assert main(["--help"]) == 0
    out = capsys.readouterr().out
    for name in (
        "systems",
        "instances",
        "configs",
        "scan",
        "metrics",
        "catalogs",
        "api",
        "context",
    ):
        assert name in out


def test_unknown_command_exits_2(capsys):
    assert main(["frobnicate"]) == 2
    assert "No such command" in capsys.readouterr().err


def test_global_flag_after_subcommand_is_accepted(env):
    # `--output` appears after the subcommand; parse_globals must still pull it.
    assert main(["context", "list", "--output", "json"]) == 0


def test_value_flag_requires_value(capsys):
    assert main(["--host"]) == 2
    assert "requires a value" in capsys.readouterr().err


def test_invalid_output_mode_exits_2(env, capsys):
    # context commands deliberately skip resolve_settings(), so validation of
    # --output is lazy: it only fires on a command that resolves settings.
    assert main(["--output", "bogus", "health"]) == 2
    assert "invalid output mode" in capsys.readouterr().err


def test_no_args_shows_help(capsys):
    assert main([]) == 0
    assert "Manage an F5 NGINX Instance Manager instance." in capsys.readouterr().out
