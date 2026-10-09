# nimctl

A CLI for **F5 NGINX Instance Manager (NIM)**. `nimctl` authenticates to a NIM
instance and drives it through the documented `/api/platform/<version>` REST API,
with JSON/raw/table output, a per-host OpenAPI spec cache, and a raw passthrough for
anything without a dedicated command.

- Python 3.11+, [`typer`](https://typer.tiangolo.com/) + `httpx`
- Config in TOML, contexts, flag → env → store precedence
- Typed exit codes

## Install

```bash
uv sync                 # create the env and install deps
uv run nimctl --help    # run from source

# or build a single-file binary
make build-exe          # -> dist/nimctl
```

Requires `uv`. Once built, replace `uv run nimctl` with `nimctl` in the examples below.

## Quick start

```bash
# 1. Point at your NIM instance and authenticate (Basic auth)
uv run nimctl context set host https://nim.example.com
uv run nimctl context set user admin
uv run nimctl context set password_file ~/.config/nimctl/admin.pw   # file holding the password
uv run nimctl context set insecure true                              # self-signed installs
uv run nimctl login

# 2. Use it
uv run nimctl systems list
uv run nimctl instances list --output table
uv run nimctl health
```

Prefer not to store anything:

```bash
uv run nimctl --host https://nim.example.com --user admin --password-file ./admin.pw --insecure systems list
```

## Configuration

Settings resolve with this precedence: **explicit flag → environment variable → stored
context → default**.

### Contexts

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
| `insecure` | `true`/`false` — skip TLS verification (self-signed installs) |

### Bearer tokens

If your org uses OIDC (e.g. Keycloak behind NGINX Plus), log in via the device-code flow —
no password or client secret needed — and nimctl saves the token for you:

```bash
uv run nimctl context set trust ./nim-ca.pem          # if the cert is self-signed
uv run nimctl login-oidc --flow code                  # opens your browser to Keycloak
uv run nimctl whoami                                  # proves the token works
uv run nimctl refresh                                 # when the short-lived token expires
```

`login-oidc` discovers the issuer and client id from NIM's own redirect to the IdP, so
you don't configure them. Two flows: `--flow code` (opens the browser; authorization-code
+ PKCE with a loopback redirect) and `--flow device` (prints a URL + code; headless).
Requirements: the client must allow the redirect URI (`http://127.0.0.1/*` for code) or
have **OAuth 2.0 Device Authorization Grant** enabled (for device). Override with
`--client-id` / `--issuer` if needed. Alternatively store a JWT obtained elsewhere with
`nimctl token set --file token.jwt`. A token takes precedence over Basic auth.

See `docs/authentication.md` for the full walkthrough: device flow, curl/password grant,
`scripts/kc-token.sh` (keeps the client secret out of the shell), and the `groups`-claim
authorization gotcha.

### Environment variables

| Variable | Purpose |
|---|---|
| `NIMCTL_HOST` | NIM base URL |
| `NIMCTL_API_VERSION` | `v1` / `v2` |
| `NIMCTL_CONTEXT` | active context name |
| `NIMCTL_USER` | Basic-auth username |
| `NIMCTL_PASSWORD` | Basic-auth password |
| `NIMCTL_TOKEN` | Bearer JWT |
| `NIMCTL_TRUST` | path to a CA bundle/PEM to trust (self-signed NIM) |
| `NIMCTL_INSECURE` | truthy → skip TLS verification |
| `NIMCTL_OUTPUT` | `json` / `raw` / `table` |
| `NIMCTL_QUIET` | truthy → suppress progress messages |
| `NIMCTL_SPEC_TTL` | OpenAPI cache TTL in seconds (default `86400`) |
| `NIMCTL_TIMEOUT` | HTTP timeout in seconds (default `30`) |
| `NIMCTL_POLL_INTERVAL` | poll interval for `--wait` in seconds (default `2`) |
| `NIMCTL_WAIT_ATTEMPTS` | max polls for `--wait` (default `60`, `scan` `300`) |

### Global options

Accept anywhere on the command line (before or after the subcommand):

```
--context TEXT      --host TEXT        --api-version TEXT   --user TEXT
--password-file PATH --token-file PATH --trust PATH          --output [json|raw|table]
--insecure / --no-insecure            --quiet               --refresh
--version           --help
```

`--refresh` forces a re-fetch of the OpenAPI spec (otherwise it is cached per host +
version under `$XDG_CACHE_HOME/nimctl/`). `--trust` points at a CA bundle/PEM to trust
in addition to the system store (use it for a self-signed NIM instead of `--insecure`).

## Usage

### Auth

```bash
uv run nimctl login                 # verifies credentials against GET /userinfo
uv run nimctl whoami                # user info as JSON
```

### Platform

```bash
uv run nimctl health                # service health
uv run nimctl modules               # installed modules
uv run nimctl modules --licensed    # licensed modules
uv run nimctl license               # license info
uv run nimctl license --status      # license status
uv run nimctl version               # API version (falls back to configured api_version)
```

### Systems

```bash
uv run nimctl systems list
uv run nimctl systems list --limit 20 --offset 40 --output table
uv run nimctl systems get <system_uid>
uv run nimctl systems tag <system_uid> --body tags.json     # PATCH /systems/{uid}
uv run nimctl systems delete <system_uid>
```

### Instances

```bash
uv run nimctl instances list --output table
uv run nimctl instances list --limit 100 --offset 0
uv run nimctl instances get <system_uid> <nginx_uid>
uv run nimctl instances list-by-system <system_uid> --limit 50
uv run nimctl instances delete <system_uid> <nginx_uid>
```

### Configurations

```bash
# fetch and inspect an instance config
uv run nimctl configs get <system_uid> <nginx_uid>
uv run nimctl configs get <system_uid> <nginx_uid> --decode /etc/nginx/conf.d/default.conf

# publish a new config (202) and optionally wait for the deployment
uv run nimctl configs publish <system_uid> <nginx_uid> --body config.json
uv run nimctl configs publish <system_uid> <nginx_uid> --body config.json --wait

uv run nimctl configs deployment <deployment_uid>
```

> `configs publish --wait` polls the deployment until it reaches a terminal state and
> exits `1` if the status is `failed` or `degraded` (details are in the rendered body).

### Scan

```bash
uv run nimctl scan start 10.0.0.0/24                 # start a subnet scan (202)
uv run nimctl scan start 10.0.0.0/24 --port 8443
uv run nimctl scan start 10.0.0.0/24 --wait          # poll until complete
uv run nimctl scan status
uv run nimctl scan cancel
```

### Metrics and catalogs

```bash
uv run nimctl metrics query --names nginx.http.request.count --start-time 2026-10-01T00:00:00Z
uv run nimctl metrics query --names nginx.http.request.count \
  --start-time 2026-10-01T00:00:00Z --end-time 2026-10-02T00:00:00Z \
  --resolution 1m --group-by "menu:instance" --dimensions "instance"

uv run nimctl catalogs show metrics                              # list metric catalog
uv run nimctl catalogs show metrics --name nginx.http.request.count
uv run nimctl catalogs show dimensions
uv run nimctl catalogs show events
```

### Security events and support IDs

Look up App Protect security events by **support ID**, or search the event feed:

```bash
uv run nimctl security support 12345678912345678911        # all events for a support ID
uv run nimctl security events --support-id 12345678912345678911
uv run nimctl security events --policy my-policy --start-time 2026-10-01T00:00:00Z
uv run nimctl security events --filter "severity >= high OR outcome=blocked"
uv run nimctl security events --id 859ad281-1844-4d52-96d6-188ad02ec322   # one event by UUID
```

`--support-id` and `--policy` are combined with `AND`. `--filter` (operators
`= != < <= >= > in not`, combined with `AND`/`OR`) is appended; `pageSize` caps at 100
(`0` disables paging). Every event carries `support_id`, `policy_name`, `violations`,
`severity`, `timestamp`, and more.

> NIM documents these endpoints as primarily for its own UI; keep usage read-only.

### Security policies, log profiles, compiler

Manage App Protect policies as NIM objects, with the policy JSON base64-encoded for you
(no `jq`/`base64` needed — this is the missing PLM bridge):

```bash
uv run nimctl security policies list
uv run nimctl security policies list --include-content
uv run nimctl security policies get <policy_uid> --decode > policy.json
uv run nimctl security policies create --name demo --file policy.json          # POST
uv run nimctl security policies create --name demo --file policy.json --update # PUT (new version)
uv run nimctl security policies delete <policy_uid>

uv run nimctl security policies bundles                       # list compiled bundles
uv run nimctl security policies download --out bundles/       # download + verify hash
uv run nimctl security policies download --uid <bundle_uid>

uv run nimctl security log-profiles list
uv run nimctl security log-profiles get <name>
uv run nimctl security log-profiles create --name lp --file log.json
uv run nimctl security log-profiles delete <name>

uv run nimctl security compiler versions
uv run nimctl security compiler versions --latest
```

`create` base64-encodes `--file` (and optional `--openapi`) into the request body.
`download` writes `<policy>.<uid8>.tgz` (or `.bundle` for non-gzip) plus a `.json`
sidecar, and fails if the bytes do not match the reported size/hash.

### Kubernetes PLM (APPolicy) conversion

NIM security policies and Kubernetes **PLM** custom resources (F5 WAF for NGINX) use the
same policy JSON — only the packaging differs. `nimctl` exchanges the base64 content;
[`v52plm.py`](~/Documents/script/v52plm.py) wraps that JSON into `APPolicy` / `APLogConf` /
`APUserSig` CRDs and back. No `jq`/`base64` needed.

```bash
# converter has one dependency (PyYAML); run it without a project env
CONV="uv run --no-project --with pyyaml python ~/Documents/script/v52plm.py"
```

**NIM → APPolicy YAML** (export a policy as a CRD):

```bash
uv run nimctl security policies list                      # find the UID
uv run nimctl security policies get <policy_uid> --decode > policy.json   # base64-decoded v5 JSON
$CONV to-crd policy.json -n security -o plm/              # -> plm/<name>-appolicy.yaml
kubectl apply -f plm/
```

**APPolicy YAML → NIM** (create a policy from a CRD):

```bash
$CONV to-json plm/demo-appolicy.yaml -o json/             # -> json/demo.json
uv run nimctl security policies create --name demo --file json/demo.json  # base64 handled for you
```

**One-liner** (NIM → cluster, piping through stdout):

```bash
uv run nimctl security policies get <policy_uid> --decode \
  | $CONV to-crd - -n security \
  | kubectl apply -f -
```

The same shape handles log profiles (`log.json` → `APLogConf`) and user signatures
(`usersigs.json` → `APUserSig`) — `detect_kind` picks the type from the top-level keys
(`policy` / `filter`+`content` / `signatures`). `v52plm.py to-crd` prints to stdout by
default (`-o DIR` writes files); `to-json` reverses any of the three. See the converter's
docstring for `check` (validate only) and `--api-version appprotect.f5.com/v1beta1`
(old NIC + WAF v4).

### Certificates

```bash
uv run nimctl certs list --limit 50
uv run nimctl certs get my-cert
uv run nimctl certs summary
uv run nimctl certs delete my-cert
```

### Instance groups

```bash
uv run nimctl instance-groups list --limit 50
uv run nimctl instance-groups get <inst_group_uid>
uv run nimctl instance-groups summary
uv run nimctl instance-groups deployment <deployment_uid>
```

### Usage and inventory

```bash
uv run nimctl usage records --nginx-uid <uid> --from 2026-10-01 --to 2026-10-08
uv run nimctl usage export --out usage.csv        # raw telemetry as CSV
uv run nimctl usage data                          # usage data with CAT information
uv run nimctl platform-config inventory            # NGINX Plus instance counts
```

### Events and platform config

```bash
uv run nimctl events list --start-time 2026-10-01T00:00:00Z --page-size 50
uv run nimctl events get <event_id>
uv run nimctl platform-config show settings
uv run nimctl staged-configs list                 # NGINX staged configurations
uv run nimctl staged-configs get <config_uid>
```

### Users, roles and groups

```bash
uv run nimctl users list --limit 50
uv run nimctl users get admin
uv run nimctl users create --body user.json
uv run nimctl users delete bob

uv run nimctl roles list --show-details
uv run nimctl roles get <name>
uv run nimctl roles features                      # module features

uv run nimctl groups list --filter admins
uv run nimctl groups get <group_name>

uv run nimctl resource-groups list --show-details
uv run nimctl resource-groups get <resource_group_uid>
```

### Raw API passthrough

Anything without a dedicated command is reachable directly. `path` is relative to
`/api/platform/<version>`. Pass query parameters with repeatable `-q/--query key=value`
(no need to embed them in the path):

```bash
uv run nimctl api tags                          # list OpenAPI tags
uv run nimctl api paths systems                 # list (METHOD, path) for a tag
uv run nimctl api spec                          # print the full OpenAPI document
uv run nimctl api call GET /systems
uv run nimctl api call POST /systems --body create.json
uv run nimctl api call PATCH /systems/<uid> --body patch.json
uv run nimctl api call GET /analytics/security/events -q filter=support_id=123 -q pageSize=10
```

Example — export all App Protect security policies (`SecurityPolicyList.items[].content`
is already base64) and decode one to a raw v5 JSON file:

```bash
uv run nimctl api call GET /security/policies > policies.json
jq -r '.items[] | select(.metadata.name=="my-policy") | .content' policies.json \
  | base64 -d > policy.json
```

For a single policy, prefer `nimctl security policies get <uid> --decode` (see
[Kubernetes PLM (APPolicy) conversion](#kubernetes-plm-apolicy-conversion) above), which
does the base64 for you.

## Command reference

Global options (above) are accepted anywhere. Arguments are positional and required
unless marked otherwise. **Bold** = required.

| Command | Arguments | Options |
|---|---|---|
| `login` | — | — |
| `login-oidc` | — | `--issuer`, `--client-id`, `--client-secret-file PATH`, `--scope`, `--flow device\|code`, `--port`, `--no-browser`, `--out PATH`, `--save/--no-save`, `--refresh-out PATH` |
| `refresh` | — | — |
| `whoami` | — | — |
| `health` | — | — |
| `modules` | — | `--licensed` |
| `license` | — | `--status` |
| `version` | — | — |
| `context list` | — | — |
| `context use` | **name** | — |
| `context set` | **key** **value** | — |
| `context show` | — | — |
| `context delete` | **name** | — |
| `context path` | — | — |
| `token set` | — | **`--file PATH`** |
| `api call` | **method** **path** | `--body PATH`, `-q/--query key=value` (repeatable) |
| `api paths` | **tag** | — |
| `api tags` | — | — |
| `api spec` | — | — |
| `systems list` | — | `--limit 0..100`, `--offset >=0` |
| `systems get` | **system_uid** | — |
| `systems tag` | **system_uid** | **`--body PATH`** |
| `systems delete` | **system_uid** | — |
| `instances list` | — | `--limit 0..100`, `--offset >=0` |
| `instances get` | **system_uid** **nginx_uid** | — |
| `instances list-by-system` | **system_uid** | `--limit 0..100` |
| `instances delete` | **system_uid** **nginx_uid** | — |
| `configs get` | **system_uid** **nginx_uid** | `--decode NAME` |
| `configs publish` | **system_uid** **nginx_uid** | **`--body PATH`**, `--wait` |
| `configs deployment` | **deployment_uid** | — |
| `scan start` | **subnet** | `--port INT`, `--wait` |
| `scan status` | — | — |
| `scan cancel` | — | — |
| `metrics query` | — | **`--names`**, `--start-time`, `--end-time`, `--resolution`, `--filter`, `--group-by`, `--dimensions` |
| `catalogs show` | **kind** (`metrics`\|`dimensions`\|`events`) | `--name NAME` |
| `security support` | **support_id** | — |
| `security events` | — | `--support-id`, `--policy`, `--filter`, `--start-time`, `--end-time`, `--page-size 0..100`, `--include-total`, `--id UUID` |
| `security policies list` | — | `--include-content`, `--versions` |
| `security policies get` | **security_policy_uid** | `--decode` |
| `security policies create` | — | **`--name`**, **`--file PATH`**, `--display-name`, `--description`, `--openapi PATH`, `--update` |
| `security policies delete` | **security_policy_uid** | — |
| `security policies bundles` | — | — |
| `security policies download` | — | `--out DIR`, `--uid UID` |
| `security log-profiles list` | — | — |
| `security log-profiles get` | **name** | — |
| `security log-profiles create` | — | **`--name`**, **`--file PATH`**, `--update` |
| `security log-profiles delete` | **name** | — |
| `security compiler versions` | — | `--latest` |
| `certs list` | — | `--limit 0..100`, `--offset >=0` |
| `certs get` | **cert_name** | — |
| `certs summary` | — | — |
| `certs delete` | **cert_name** | — |
| `instance-groups list` | — | `--limit 0..100`, `--offset >=0` |
| `instance-groups get` | **inst_group_uid** | — |
| `instance-groups summary` | — | — |
| `instance-groups deployment` | **deployment_uid** | — |
| `usage records` | — | `--limit 0..100`, `--offset >=0`, `--nginx-uid`, `--from`, `--to` |
| `usage export` | — | `--out PATH` |
| `usage data` | — | — |
| `platform-config show` | **config_name** | — |
| `platform-config inventory` | — | — |
| `events list` | — | `--start-time`, `--end-time`, `--filter`, `--order-by`, `--page-size 0..100`, `--include-total` |
| `events get` | **event_id** | — |
| `staged-configs list` | — | — |
| `staged-configs get` | **config_uid** | — |
| `users list` | — | `--limit 0..100`, `--offset >=0`, `--source` |
| `users get` | **user_name** | — |
| `users create` | — | **`--body PATH`** |
| `users delete` | **user_name** | — |
| `roles list` | — | `--show-details` |
| `roles get` | **name** | — |
| `roles features` | — | — |
| `groups list` | — | `--limit 0..100`, `--offset >=0`, `--filter` |
| `groups get` | **group_name** | — |
| `resource-groups list` | — | `--limit 0..100`, `--offset >=0`, `--show-details`, `--name-filter` |
| `resource-groups get` | **resource_group_uid** | — |

## Output modes

- `json` (default) — pretty-printed JSON
- `raw` — minimal printing (strings verbatim, objects as compact JSON)
- `table` — tab-separated columns; only for commands that define columns
  (`systems`, `instances`)

```bash
uv run nimctl systems list --output table
uv run nimctl systems list --output raw
```

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

## Development

```bash
make test        # uv run pytest
make lint        # uv run ruff check src
make build-exe   # uv run pyinstaller --onefile --name nimctl --paths src entry.py
make clean
```

Tests use `pytest` with an `httpx.MockTransport` fake (`tests/conftest.py`); no live
NIM is required. Run the whole suite with:

```bash
uv run pytest
uv run ruff check src tests
```

## Notes

- Secrets are never echoed and are read from files (or the environment), never from
  `argv`.
- The OpenAPI spec is cached per host+version at `$XDG_CACHE_HOME/nimctl/spec-<hash>.json`;
  use `--refresh` to force a re-fetch.
- HTTP errors surface as `HTTP <status>: <message>` and map to the exit codes above.
