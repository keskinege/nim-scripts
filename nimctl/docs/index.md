---
title: nimctl
---

# nimctl

A CLI for **F5 NGINX Instance Manager (NIM)**. `nimctl` authenticates to a NIM
instance and drives it through the documented `/api/platform/<version>` REST API,
with JSON/raw/table output, a per-host OpenAPI spec cache, and a raw passthrough for
anything without a dedicated command.

- Python 3.11+, [`typer`](https://typer.tiangolo.com/) + `httpx`
- Config in TOML, contexts, flag → env → store precedence
- Typed exit codes

## Where to go next

- [Getting started](getting-started.md) — install, authenticate, first commands.
- [Configuration](configuration.md) — contexts, environment variables, global options.
- [CLI reference](reference/cli.md) — every command, argument and option.

## What it covers

| Area | Commands |
|---|---|
| Auth | `login`, `login-oidc`, `refresh`, `whoami`, `token set` |
| Contexts | `context list/use/set/show/delete/path` |
| Systems / instances | `systems …`, `instances …` |
| Instance config | `configs get/publish/deployment` |
| Scan | `scan start/status/cancel` |
| Metrics / catalogs / events | `metrics query`, `catalogs show`, `events list/get` |
| Security | `security support/events`, `security policies …`, `security log-profiles …`, `security compiler versions` |
| Certs / groups / usage | `certs …`, `instance-groups …`, `usage …`, `platform-config …` |
| Admin | `users …`, `roles …`, `groups …`, `resource-groups …` |
| Raw API | `api call/paths/tags/spec` |

See the [CLI reference](reference/cli.md) for the full list.
