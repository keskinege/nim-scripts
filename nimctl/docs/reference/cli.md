---
title: CLI reference
---

# CLI reference

Generated from the live Typer app — regenerate with
`uv run python scripts/gen_command_reference.py`.
Global options (`--host`, `--context`, `--output`, …) are accepted anywhere on
the command line; see [Configuration](../configuration.md).

### `nimctl login`


### `nimctl login-oidc`

Log in via OIDC (browser authorization-code or device code) and save the token.

- `--issuer` `<str>`
- `--client-id` `<str>`
- `--client-secret-file` `<file>`
- `--scope` `<str>` (default `openid profile email`)
- `--flow` `<str>` (default `device`)
- `--port` `<int>` (default `0`)
- `--no-browser`
- `--out` `<path>`
- `--save`, `--no-save`
- `--refresh-out` `<path>`

### `nimctl refresh`

Refresh the stored access token using the saved refresh token.


### `nimctl whoami`


### `nimctl health`


### `nimctl modules`

- `--licensed`

### `nimctl license`

- `--status`

### `nimctl version`


### `nimctl context`

Manage connection contexts.


Subcommands: `list`, `use`, `set`, `show`, `delete`, `path`

### `nimctl context list`


### `nimctl context use`

- `name` `<str>` **(required)**

### `nimctl context set`

- `key` `<str>` **(required)**
- `value` `<str>` **(required)**

### `nimctl context show`


### `nimctl context delete`

- `name` `<str>` **(required)**

### `nimctl context path`


### `nimctl token`

Manage bearer tokens.


Subcommands: `set`

### `nimctl token set`

- `--file` `<file>` **(required)**

### `nimctl api`

Raw API passthrough and OpenAPI introspection.


Subcommands: `call`, `paths`, `tags`, `spec`

### `nimctl api call`

- `method` `<str>` **(required)**
- `path` `<str>` **(required)**
- `--body` `<file>`
- `--query`, `-q` `<str>` (default `[]`)

### `nimctl api paths`

- `tag` `<str>` **(required)**

### `nimctl api tags`


### `nimctl api spec`


### `nimctl systems`

Manage systems.


Subcommands: `list`, `get`, `tag`, `delete`

### `nimctl systems list`

- `--limit` `<int range>`
- `--offset` `<int range>`

### `nimctl systems get`

- `system_uid` `<str>` **(required)**

### `nimctl systems tag`

- `system_uid` `<str>` **(required)**
- `--body` `<file>` **(required)**

### `nimctl systems delete`

- `system_uid` `<str>` **(required)**

### `nimctl instances`

Manage NGINX instances.


Subcommands: `list`, `get`, `list-by-system`, `delete`

### `nimctl instances list`

- `--limit` `<int range>`
- `--offset` `<int range>`

### `nimctl instances get`

- `system_uid` `<str>` **(required)**
- `nginx_uid` `<str>` **(required)**

### `nimctl instances list-by-system`

- `system_uid` `<str>` **(required)**
- `--limit` `<int range>`

### `nimctl instances delete`

- `system_uid` `<str>` **(required)**
- `nginx_uid` `<str>` **(required)**

### `nimctl configs`

Manage NGINX configurations.


Subcommands: `get`, `publish`, `deployment`

### `nimctl configs get`

- `system_uid` `<str>` **(required)**
- `nginx_uid` `<str>` **(required)**
- `--decode` `<str>`

### `nimctl configs publish`

- `system_uid` `<str>` **(required)**
- `nginx_uid` `<str>` **(required)**
- `--body` `<file>` **(required)**
- `--wait`

### `nimctl configs deployment`

- `deployment_uid` `<str>` **(required)**

### `nimctl scan`

Scan for NGINX instances.


Subcommands: `start`, `status`, `cancel`

### `nimctl scan start`

- `subnet` `<str>` **(required)**
- `--port` `<int>`
- `--wait`

### `nimctl scan status`


### `nimctl scan cancel`


### `nimctl metrics`

Query metrics.


Subcommands: `query`

### `nimctl metrics query`

- `--names` `<str>` **(required)**
- `--start-time` `<str>`
- `--end-time` `<str>`
- `--resolution` `<str>`
- `--filter` `<str>`
- `--group-by` `<str>`
- `--dimensions` `<str>`

### `nimctl catalogs`

Query metrics, dimension and event catalogs.


Subcommands: `show`

### `nimctl catalogs show`

- `kind` `<str>` **(required)**
- `--name` `<str>`

### `nimctl security`

App Protect security: events, policies, log profiles.


Subcommands: `support`, `events`, `policies`, `log-profiles`, `compiler`

### `nimctl security support`

List the security events recorded for one support ID.

- `support_id` `<str>` **(required)**

### `nimctl security events`

Search security events, or fetch one event with --id.

- `--support-id` `<str>`
- `--policy` `<str>`
- `--filter` `<str>`
- `--start-time` `<str>`
- `--end-time` `<str>`
- `--page-size` `<int range>`
- `--include-total`
- `--id` `<str>`

### `nimctl security policies`

Manage App Protect security policies.


Subcommands: `list`, `get`, `create`, `delete`, `bundles`, `download`

### `nimctl security policies list`

- `--include-content`
- `--versions` `<str>`

### `nimctl security policies get`

- `security_policy_uid` `<str>` **(required)**
- `--decode`

### `nimctl security policies create`

Create (or update) a NIM security policy from a local policy JSON file.

- `--name` `<str>` **(required)**
- `--file` `<file>` **(required)**
- `--display-name` `<str>`
- `--description` `<str>`
- `--openapi` `<file>`
- `--update`

### `nimctl security policies delete`

- `security_policy_uid` `<str>` **(required)**

### `nimctl security policies bundles`


### `nimctl security policies download`

Download compiled policy bundles (hash-verified) plus a metadata sidecar.

- `--out` `<path>` (default `bundles`)
- `--uid` `<str>`

### `nimctl security log-profiles`

Manage App Protect log profiles.


Subcommands: `list`, `get`, `create`, `delete`

### `nimctl security log-profiles list`


### `nimctl security log-profiles get`

- `log_profile_name` `<str>` **(required)**

### `nimctl security log-profiles create`

- `--name` `<str>` **(required)**
- `--file` `<file>` **(required)**
- `--update`

### `nimctl security log-profiles delete`

- `log_profile_name` `<str>` **(required)**

### `nimctl security compiler`

App Protect compiler versions.


Subcommands: `versions`

### `nimctl security compiler versions`

- `--latest`

### `nimctl certs`

Manage certificates.


Subcommands: `list`, `get`, `summary`, `delete`

### `nimctl certs list`

- `--limit` `<int range>`
- `--offset` `<int range>`

### `nimctl certs get`

- `cert_name` `<str>` **(required)**

### `nimctl certs summary`


### `nimctl certs delete`

- `cert_name` `<str>` **(required)**

### `nimctl instance-groups`

Manage NGINX instance groups.


Subcommands: `list`, `get`, `summary`, `deployment`

### `nimctl instance-groups list`

- `--limit` `<int range>`
- `--offset` `<int range>`

### `nimctl instance-groups get`

- `inst_group_uid` `<str>` **(required)**

### `nimctl instance-groups summary`


### `nimctl instance-groups deployment`

- `deployment_uid` `<str>` **(required)**

### `nimctl usage`

Query NGINX usage telemetry.


Subcommands: `records`, `export`, `data`

### `nimctl usage records`

- `--limit` `<int range>`
- `--offset` `<int range>`
- `--nginx-uid` `<str>`
- `--from` `<str>`
- `--to` `<str>`

### `nimctl usage export`

- `--out` `<path>`

### `nimctl usage data`


### `nimctl events`

Query analytics events.


Subcommands: `list`, `get`

### `nimctl events list`

- `--start-time` `<str>`
- `--end-time` `<str>`
- `--filter` `<str>`
- `--order-by` `<str>`
- `--page-size` `<int range>`
- `--include-total`

### `nimctl events get`

- `event_id` `<str>` **(required)**

### `nimctl platform-config`

Query the platform configuration and inventory.


Subcommands: `show`, `inventory`

### `nimctl platform-config show`

- `config_name` `<str>` **(required)**

### `nimctl platform-config inventory`


### `nimctl staged-configs`

List NGINX staged configurations.


Subcommands: `list`, `get`

### `nimctl staged-configs list`


### `nimctl staged-configs get`

- `config_uid` `<str>` **(required)**

### `nimctl users`

Manage users.


Subcommands: `list`, `get`, `create`, `delete`

### `nimctl users list`

- `--limit` `<int range>`
- `--offset` `<int range>`
- `--source` `<str>`

### `nimctl users get`

- `user_name` `<str>` **(required)**

### `nimctl users create`

- `--body` `<file>` **(required)**

### `nimctl users delete`

- `user_name` `<str>` **(required)**

### `nimctl roles`

Manage roles and module features.


Subcommands: `list`, `get`, `features`

### `nimctl roles list`

- `--show-details`

### `nimctl roles get`

- `name` `<str>` **(required)**

### `nimctl roles features`


### `nimctl groups`

Manage authentication groups.


Subcommands: `list`, `get`

### `nimctl groups list`

- `--limit` `<int range>`
- `--offset` `<int range>`
- `--filter` `<str>`

### `nimctl groups get`

- `group_name` `<str>` **(required)**

### `nimctl resource-groups`

Manage resource groups.


Subcommands: `list`, `get`

### `nimctl resource-groups list`

- `--limit` `<int range>`
- `--offset` `<int range>`
- `--show-details`
- `--name-filter` `<str>`

### `nimctl resource-groups get`

- `resource_group_uid` `<str>` **(required)**
