from __future__ import annotations

import sys
from pathlib import Path

import click
import typer

from . import __version__
from .config import GlobalOptions, set_globals
from .errors import NimctlError

_USAGE_ERRORS: tuple[type[BaseException], ...] = (click.UsageError,)
_EXIT_ERRORS: tuple[type[BaseException], ...] = (click.exceptions.Exit,)
try:
    from typer import _click as _typer_click

    _USAGE_ERRORS = (*_USAGE_ERRORS, _typer_click.exceptions.UsageError)
    _EXIT_ERRORS = (*_EXIT_ERRORS, _typer_click.exceptions.Exit)
except Exception:
    pass

app = typer.Typer(
    no_args_is_help=True,
    add_completion=False,
    help="Manage an F5 NGINX Instance Manager instance.",
)

_VALUE_FLAGS = {
    "--context": "context",
    "--host": "host",
    "--api-version": "api_version",
    "--user": "user",
    "--password-file": "password_file",
    "--token-file": "token_file",
    "--trust": "trust",
    "--output": "output",
}
_BOOL_FLAGS = {
    "--insecure": ("insecure", True),
    "--no-insecure": ("insecure", False),
    "--quiet": ("quiet", True),
    "--refresh": ("refresh", True),
}


def parse_globals(argv: list[str]) -> tuple[GlobalOptions, list[str]]:
    options = GlobalOptions()
    rest: list[str] = []
    i = 0
    while i < len(argv):
        arg = argv[i]
        name, has_eq, inline = arg.partition("=")
        if name in _VALUE_FLAGS:
            if has_eq:
                value = inline
            else:
                i += 1
                if i >= len(argv):
                    raise click.UsageError(f"{name} requires a value")
                value = argv[i]
            attr = _VALUE_FLAGS[name]
            setattr(options, attr, Path(value) if attr.endswith("_file") else value)
        elif name in _BOOL_FLAGS:
            attr, value = _BOOL_FLAGS[name]
            setattr(options, attr, value)
        else:
            rest.append(arg)
        i += 1
    return options, rest


@app.callback(invoke_without_command=True)
def _root(version: bool = typer.Option(False, "--version", help="Show version and exit.")) -> None:
    if version:
        click.echo(f"nimctl {__version__}")
        raise typer.Exit()


def _register() -> None:
    from .commands import (
        api,
        auth,
        catalogs,
        certs,
        configs,
        context,
        events,
        groups,
        instance_groups,
        instances,
        metrics,
        platform,
        platform_config,
        resource_groups,
        roles,
        scan,
        security,
        staged_configs,
        systems,
        usage,
        users,
    )

    app.add_typer(context.app, name="context")
    app.command("login")(auth.login)
    app.command("login-oidc")(auth.login_oidc)
    app.command("refresh")(auth.refresh)
    app.command("whoami")(auth.whoami)
    app.add_typer(auth.token_app, name="token")
    app.add_typer(api.app, name="api")
    app.add_typer(systems.app, name="systems")
    app.add_typer(instances.app, name="instances")
    app.add_typer(configs.app, name="configs")
    app.add_typer(scan.app, name="scan")
    app.add_typer(metrics.app, name="metrics")
    app.add_typer(catalogs.app, name="catalogs")
    app.add_typer(security.app, name="security")
    app.add_typer(certs.app, name="certs")
    app.add_typer(instance_groups.app, name="instance-groups")
    app.add_typer(usage.app, name="usage")
    app.add_typer(events.app, name="events")
    app.add_typer(platform_config.app, name="platform-config")
    app.add_typer(staged_configs.app, name="staged-configs")
    app.add_typer(users.app, name="users")
    app.add_typer(roles.app, name="roles")
    app.add_typer(groups.app, name="groups")
    app.add_typer(resource_groups.app, name="resource-groups")
    for name, command in (
        ("health", platform.health),
        ("modules", platform.modules),
        ("license", platform.license_cmd),
        ("version", platform.version),
    ):
        app.command(name)(command)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        options, rest = parse_globals(argv)
        set_globals(options)
        _register()
        app(rest or ["--help"], standalone_mode=False)
    except _USAGE_ERRORS as exc:
        click.echo(f"nimctl: {exc.format_message()}", err=True)
        return 2
    except _EXIT_ERRORS as exc:
        return exc.exit_code
    except NimctlError as exc:
        click.echo(f"nimctl: {exc}", err=True)
        return exc.exit_code
    return 0


def run() -> None:
    raise SystemExit(main())


if __name__ == "__main__":
    run()
