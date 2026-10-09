#!/usr/bin/env python3
"""Generate docs/reference/cli.md from the live Click/Typer command tree.

Run from the repo root:  uv run python scripts/gen_command_reference.py
"""

from __future__ import annotations

from pathlib import Path

import click
from typer.main import get_command

from nimctl.cli import _register, app


def _params(cmd: click.Command) -> list[str]:
    rows: list[str] = []
    for p in cmd.params:
        if hasattr(p, "opts"):  # Option (TyperOption/click.Option)
            flags = ", ".join(
                f"`{o}`" for o in list(p.opts) + list(getattr(p, "secondary_opts", []))
            )
            if getattr(p, "is_flag", False):
                rows.append(f"- {flags}")
            else:
                kind = p.type.name if getattr(p, "type", None) else "text"
                req = " **(required)**" if getattr(p, "required", False) else ""
                default = ""
                if p.default not in (None, (), ""):
                    default = f" (default `{p.default}`)"
                rows.append(f"- {flags} `<{kind}>`{req}{default}")
        else:  # Argument
            suffix = " (required)" if getattr(p, "required", False) else ""
            rows.append(f"- `{p.name.upper()}`{suffix}")
    return rows


def _walk(cmd: click.Command, path: str, out: list[str]) -> None:
    out.append(f"### `{path}`\n")
    helptext = (cmd.help or cmd.get_short_help_str() or "").strip()
    if helptext:
        out.append(helptext.split("\n\n")[0].replace("\n", " ") + "\n")
    for row in _params(cmd):
        out.append(row)
    subs_map = getattr(cmd, "commands", None)
    if subs_map:
        subs = ", ".join(f"`{n}`" for n in subs_map)
        out.append(f"\nSubcommands: {subs}")
    out.append("")
    if subs_map:
        for sub in subs_map.values():
            _walk(sub, f"{path} {sub.name}", out)


def main() -> int:
    _register()
    click_group: click.Group = get_command(app)
    out = [
        "---",
        "title: CLI reference",
        "---",
        "",
        "# CLI reference",
        "",
        "Generated from the live Typer app — regenerate with",
        "`uv run python scripts/gen_command_reference.py`.",
        "Global options (`--host`, `--context`, `--output`, …) are accepted anywhere on",
        "the command line; see [Configuration](../configuration.md).",
        "",
    ]
    for name, cmd in click_group.commands.items():
        _walk(cmd, f"nimctl {name}", out)
    Path("docs/reference/cli.md").write_text("\n".join(out).rstrip() + "\n")
    print("wrote docs/reference/cli.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
