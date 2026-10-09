---
title: Getting started
---

# Getting started

## Prerequisites

- Python 3.11+
- [`uv`](https://docs.astral.sh/uv/) for the env/lock/build workflow
- Network access to a F5 NGINX Instance Manager instance

## Install

```bash
uv sync                 # create the env and install deps
uv run nimctl --help    # run from source

# or build a single-file binary
make build-exe          # -> dist/nimctl
```

Once built, replace `uv run nimctl` with `nimctl` in the examples below.

## Authenticate

```bash
uv run nimctl context set host https://nim.example.com
uv run nimctl context set user admin
uv run nimctl context set password_file ~/.config/nimctl/admin.pw   # file holding the password
uv run nimctl context set insecure true                              # self-signed installs
uv run nimctl login
```

Prefer not to store anything:

```bash
uv run nimctl --host https://nim.example.com --user admin --password-file ./admin.pw --insecure systems list
```

## First commands

```bash
uv run nimctl health
uv run nimctl systems list
uv run nimctl instances list --output table
```

## Next steps

- [Configuration](configuration.md) — contexts, env vars, global options.
- [CLI reference](reference/cli.md) — every command, argument and option.
- [Development](#development) — tests and linting.

## Development

```bash
make test        # uv run pytest
make lint        # uv run ruff check src
make build-exe   # uv run pyinstaller --onefile --name nimctl --paths src entry.py
make clean
```

Tests use `pytest` with an `httpx.MockTransport` fake (`tests/conftest.py`); no live
NIM is required.

```bash
uv run pytest
uv run ruff check src tests
```
