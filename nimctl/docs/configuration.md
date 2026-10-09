---
title: Configuration
---

# Configuration

Settings resolve with this precedence: **explicit flag → environment variable → stored
context → default**.

## Contexts

Contexts live in `$XDG_CONFIG_HOME/nimctl/config.toml`
(default `~/.config/nimctl/config.toml`) and are written `0600`.

```bash
uv run nimctl context set host https://nim.example.com
uv run nimctl context set api_version v1
uv run nimctl context set user admin
uv run nimctl context set password_file ~/.config/nimctl/admin.pw
uv run nimctl context set token_file ~/.config/nimctl/token.jwt
uv run nimctl context set insecure true
uv run nimctl context show              # print the active context
uv run nimctl context path              # print the config file path

# multiple contexts
uv run nimctl --context prod context set host https://prod.example.com
uv run nimctl context use prod
uv run nimctl context list
uv run nimctl context delete prod
```

| `context set` key | meaning |
|---|---|
| `host` | NIM base URL (no trailing `/api/...`) |
| `api_version` | `v1` (default) or `v2` |
| `user` | Basic-auth username |
| `password_file` | file whose contents are the password |
| `token_file` | file whose contents are a Bearer JWT |
| `trust` | CA bundle/PEM to trust (self-signed NIM) |
| `oidc_issuer` | OIDC issuer URL (for `login-oidc`/`refresh`) |
| `oidc_client_id` | OIDC client id |
| `insecure` | `true`/`false` — skip TLS verification |

## Bearer tokens

A token takes precedence over Basic auth when both are set.

```bash
uv run nimctl token set --file ~/.config/nimctl/token.jwt
uv run nimctl whoami
```

## Environment variables

| Variable | Purpose |
|---|---|
| `NIMCTL_HOST` | NIM base URL |
| `NIMCTL_API_VERSION` | `v1` / `v2` |
| `NIMCTL_CONTEXT` | active context name |
| `NIMCTL_USER` | Basic-auth username |
| `NIMCTL_PASSWORD` | Basic-auth password |
| `NIMCTL_TOKEN` | Bearer JWT |
| `NIMCTL_TRUST` | path to a CA bundle/PEM to trust (self-signed NIM) |
| `NIMCTL_OIDC_ISSUER` | OIDC issuer URL |
| `NIMCTL_OIDC_CLIENT_ID` | OIDC client id |
| `NIMCTL_INSECURE` | truthy → skip TLS verification |
| `NIMCTL_OUTPUT` | `json` / `raw` / `table` |
| `NIMCTL_QUIET` | truthy → suppress progress messages |
| `NIMCTL_SPEC_TTL` | OpenAPI cache TTL in seconds (default `86400`) |
| `NIMCTL_TIMEOUT` | HTTP timeout in seconds (default `30`) |
| `NIMCTL_POLL_INTERVAL` | poll interval for `--wait` in seconds (default `2`) |
| `NIMCTL_WAIT_ATTEMPTS` | max polls for `--wait` (default `60`, `scan` `300`) |

## Global options

Accepted anywhere on the command line (before or after the subcommand):

| Option | Meaning |
|---|---|
| `--context TEXT` | active context name |
| `--host TEXT` | NIM base URL |
| `--api-version TEXT` | `v1` / `v2` |
| `--user TEXT` | Basic-auth username |
| `--password-file PATH` | file holding the password |
| `--token-file PATH` | file holding a Bearer JWT |
| `--trust PATH` | CA bundle/PEM to trust in addition to the system store (self-signed NIM) |
| `--output [json\|raw\|table]` | output mode (default `json`) |
| `--insecure` / `--no-insecure` | skip / require TLS verification |
| `--quiet` | suppress progress messages |
| `--refresh` | force OpenAPI spec re-fetch |
| `--version` / `--help` | version / help |

## Output modes

- `json` (default) — pretty-printed JSON
- `raw` — minimal printing (strings verbatim, objects as compact JSON)
- `table` — tab-separated columns (only for commands that define columns)

## Exit codes

| Code | Meaning |
|---|---|
| `0` | success |
| `1` | generic / network / config / terminal deployment failure |
| `2` | usage error (bad flag or value, unknown command) |
| `3` | authentication (401/403) |
| `4` | not found (404) |
| `5` | conflict (409) |
| `6` | server error (5xx) |
