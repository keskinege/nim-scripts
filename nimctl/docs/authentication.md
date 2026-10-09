---
title: Authentication
---

# Authentication

nimctl supports the two schemes NIM accepts, and auto-selects between them:

```text
Basic auth  -> Authorization: Basic base64(user:password)
OIDC        -> Authorization: Bearer <JWT from the IdP>
```

If your NIM is fronted by **NGINX Plus with OIDC** (typically **Keycloak**), Basic auth is
disabled and every API call must carry a Bearer JWT. This page covers that case.

## 1. Trust the NIM certificate

A self-signed NIM endpoint fails TLS verification. Trust its CA **in addition to** the
system store (which you still need for the IdP's public certificate, e.g. Let's Encrypt):

```bash
# capture the leaf certificate (or use the CA that signed it)
openssl s_client -connect nginx-ic.tail7fa79.ts.net:443 -showcerts \
  </dev/null 2>/dev/null | sed -n '/BEGIN CERTIFICATE/,/END CERTIFICATE/p' > nim-ca.pem

uv run nimctl context set trust ./nim-ca.pem     # trusted in addition to the system store
# alternatives:  --trust PATH   |   NIMCTL_TRUST=...   |   context set trust ...
```

`--trust PATH` / `NIMCTL_TRUST` / `context set trust` **appends** the CA/PEM to the system
trust store (it does not replace it), so both a self-signed NIM **and** a publicly-signed
Keycloak verify. `--insecure` skips verification entirely (only for quick testing) and wins
over `--trust`.

!!! warning "Don't point --trust at a file that only has the other side's cert"
    If `--trust` *replaced* the system store, connecting to a public IdP would fail with
    `unable to get local issuer certificate`. nimctl keeps the system store, so a file
    holding just NIM's self-signed cert is enough.

## 2. Get a Keycloak token

nimctl can run the OIDC **device-code flow** for you (`login-oidc`, recommended), or you
obtain a token with curl. Values below come from your setup (issuer
`https://keycloak.tail7fa79.ts.net/auth/realms/my-realm`, NIM
`https://nginx-ic.tail7fa79.ts.net`).

For discovery (endpoints differ by Keycloak version):

```bash
curl -fsS https://keycloak.tail7fa79.ts.net/auth/realms/my-realm/.well-known/openid-configuration
# note token_endpoint / authorization_endpoint — older Keycloak keeps /auth/, newer drops it
```

### Option 0 — `nimctl login-oidc` (recommended)

You do **not** need to configure the issuer or client id yourself: an unauthenticated
request to NIM answers `302` with a `Location` pointing at the IdP's authorization
endpoint, which names both. nimctl reads it automatically:

```
Location: https://keycloak…/auth/realms/my-realm/protocol/openid-connect/auth
          ?client_id=my-client&response_type=code&redirect_uri=https://<nim>:443/_codexch&…
```

So just point at the service:

```bash
uv run nimctl context set trust ./nim-ca.pem          # NIM/Keycloak self-signed (appended)
uv run nimctl login-oidc
```

Two flows are supported via `--flow`:

- **`--flow code` (browser)** — nimctl starts a loopback listener
  (`http://127.0.0.1:<port>/callback`), opens the browser at Keycloak, waits for you to
  log in, catches the redirect, and exchanges the code (authorization-code + **PKCE**).
  This is the "open a web page, log in" flow.
- **`--flow device` (default)** — prints a URL + user code; you approve in a browser on
  any device, and nimctl polls for the token. Headless-friendly, no client secret.

```bash
uv run nimctl login-oidc --flow code            # opens the browser
uv run nimctl login-oidc --flow code --no-browser   # print the URL instead
uv run nimctl login-oidc --flow device
```

!!! warning "Keycloak client configuration"
    Either flow needs the client to be allowed:
    - **`--flow code`:** add the loopback redirect to **Valid redirect URIs**, e.g.
      `http://127.0.0.1/*` (Keycloak 24+ allows `http://127.0.0.1` and
      `http://localhost` by default only if configured). Symptom if missing:
      `400 Invalid parameter: redirect_uri`.
    - **`--flow device`:** enable **OAuth 2.0 Device Authorization Grant** under
      *Capability config*. Symptom if missing: `401 Invalid client or Invalid client credentials`.

    And if the client is **confidential** (has a client secret — e.g. NIM's own
    `my-client`, which NGINX OIDC configures with `OIDC_CLIENT_SECRET`), the token
    exchange/auth requires that secret:
    `401 unauthorized_client "Invalid client or Invalid client credentials"`.
    Pass it with `--client-secret-file`:

    ```bash
    uv run nimctl login-oidc --flow code --client-secret-file ~/.config/nimctl/my-client.secret
    ```

    Or create a **public** client (no secret) for the CLI to avoid handling one at all.

What it does: discovers issuer + client id from NIM's redirect (falling back to
`--issuer`/`--client-id`/context), fetches the issuer's endpoints, runs the chosen flow,
then writes the access token (`--out`, default `~/.config/nimctl/nim.token`) and refresh
token (`--refresh-out`, default `<token>.refresh`) as `0600` and stores
`oidc_issuer` / `oidc_client_id` / `token_file` in the active context.

Then refresh when the (short-lived) token expires:

```bash
uv run nimctl refresh        # uses the stored refresh token, rewrites the access token
```

### Option A — dedicated confidential client (scripted / CI)

Create a Keycloak client for the CLI with **Standard flow** + **Direct access grants**
enabled. Public clients usually also work for the password grant:

```bash
TOKEN_EP=https://keycloak.tail7fa79.ts.net/auth/realms/my-realm/protocol/openid-connect/token
CLIENT=cliapp                      # your client id
SECRET='<client-secret>'           # only if the client is confidential
read -rsp 'password: ' KC_PASS; echo

curl -fsS -X POST "$TOKEN_EP" \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  --data-urlencode grant_type=password \
  --data-urlencode client_id="$CLIENT" \
  --data-urlencode client_secret="$SECRET" \
  --data-urlencode username="$USER" \
  --data-urlencode password="$KC_PASS" \
  --data-urlencode scope=openid profile email \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])' > token.jwt
```

### Option B — interactive (browser) when ROPC is disabled / MFA

1. Open the Keycloak authorization URL (values from `…/openid-configuration`) in a browser:
   `https://keycloak.tail7fa79.ts.net/auth/realms/my-realm/protocol/openid-connect/auth?client_id=nim-vm&response_type=code&scope=openid&redirect_uri=https://nginx-ic.tail7fa79.ts.net/`
2. After login, copy the JWT from the browser: log into the NIM UI, open DevTools →
   Network, and copy the `Authorization: Bearer …` header from an API call into `token.jwt`.

## 3. Store the token and use the API

```bash
uv run nimctl token set --file token.jwt     # stored for the active context
uv run nimctl whoami                          # GET /userinfo  (proves auth)
uv run nimctl health
uv run nimctl systems list --output table
```

Per-invocation (no stored state):

```bash
uv run nimctl --host https://nginx-ic.tail7fa79.ts.net \
  --token-file token.jwt --trust ./nim-ca.pem systems list
```

Env only (CI-friendly):

```bash
export NIMCTL_HOST=https://nginx-ic.tail7fa79.ts.net
export NIMCTL_TOKEN="$(cat token.jwt)"
export NIMCTL_TRUST=./nim-ca.pem
uv run nimctl systems list
```

## 4. Keeping client_id / client_secret out of the shell

OAuth treats **`client_id` as public** (it rides in browser URLs and every token
request). The **`client_secret`** is the credential. To keep it off the command line —
and therefore out of shell history, `ps`, and CI logs:

**Preferred — no secret at all.** Prefer a **public** client using the *device code* or
*authorization code + PKCE* grant. Your realm advertises
`urn:ietf:params:oauth:grant-type:device_code`; enable "Device Authorization Grant" on a
public client and no client secret exists to leak:

```bash
# 1. ask for a device + user code (no secret)
curl -sS -X POST "$DEVICE_EP" \
  -d client_id=nim-cli -d scope=openid
# 2. the user visits verification_uri and enters user_code
# 3. poll the token endpoint with the device_code until it returns an access_token
```

**If you must use a confidential client**, store the secret in a `0600` file (or the OS
keychain / a secret manager) and hand curl the *file*, never the value. `scripts/kc-token.sh`
does this for you:

```bash
mkdir -p ~/.config/nimctl && chmod 700 ~/.config/nimctl

# secret + password live in 0600 files, NOT in the config or the shell history
printf '%s' '<client-secret>' > ~/.config/nimctl/cliapp.secret && chmod 600 ~/.config/nimctl/cliapp.secret
printf '%s' '<password>'      > ~/.config/nimctl/alice.pw      && chmod 600 ~/.config/nimctl/alice.pw

cat > ~/.config/nimctl/kc.env <<'EOF'
KC_TOKEN_ENDPOINT=https://keycloak.tail7fa79.ts.net/auth/realms/my-realm/protocol/openid-connect/token
KC_CLIENT_ID=cliapp
KC_CLIENT_SECRET_FILE=/home/you/.config/nimctl/cliapp.secret
KC_USERNAME=alice
KC_PASSWORD_FILE=/home/you/.config/nimctl/alice.pw
EOF
chmod 600 ~/.config/nimctl/kc.env

scripts/kc-token.sh --out token.jwt          # writes token.jwt + refresh (both 0600)
uv run nimctl token set --file token.jwt
```

Key points the script enforces:

- The secret is read from a file and passed to curl as `--data-urlencode client_secret@<file>`,
  so **only a file path reaches argv** (verified: `ps` shows `client_secret@/tmp/…`, not the value).
- It refuses to echo the secret or the raw response; output files are `0600` (`umask 077`).
- It warns if the config is not mode `600`.

Other stores, all injected as files/env at runtime (never committed):

| Store | Example |
|---|---|
| macOS Keychain | `SECRET=$(security find-generic-password -s keycloak-cliapp -w)` |
| 1Password CLI | `SECRET=$(op read 'op://Private/keycloak-cliapp/credential')` |
| SOPS / age | `SECRET=$(sops -d secrets.enc.yaml \| yq .kc_secret)` |
| Vault | `SECRET=$(vault kv get -field=secret kv/keycloak/cliapp)` |
| CI | repo/environment secret injected as a file, not a plaintext env var |

**Never** put the secret in `--client-secret ...` (argv → history + `ps`), and prefer a
file over `KC_CLIENT_SECRET`/`NIMCTL_*` env (env is readable by same-user processes and
often captured in crash dumps/logs). `client_id` may live in config freely.

## 5. Access-token lifetime and refresh

Keycloak access tokens are short-lived (default ~5 min). Refresh before expiry:

```bash
TOKEN_EP=https://keycloak.tail7fa79.ts.net/auth/realms/my-realm/protocol/openid-connect/token
curl -fsS -X POST "$TOKEN_EP" \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  --data-urlencode grant_type=refresh_token \
  --data-urlencode client_id=cliapp --data-urlencode client_secret="$SECRET" \
  --data-urlencode refresh_token="$(cat refresh.jwt)" \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])' > token.jwt
```

`nimctl` re-reads the token file on every command, so just overwrite it after refreshing.

## 6. Authorization — the `groups` claim

Authentication can succeed while access is **denied**: NIM maps the token's `groups` claim to
NIM user groups (exact-name match) and only grants whatever those groups allow (e.g. an
`admin` group with the `admin` role). `401` means the token itself was rejected; `403` usually
means the `groups` claim doesn't match a NIM group.

```bash
cut -d. -f2 token.jwt | tr '_-' '/+' | base64 -d 2>/dev/null | python3 -m json.tool
```

In Keycloak, add a **group membership** mapper so the client emits `groups`, and create a
matching group in NIM holding the `admin` role.

## Exit codes

| Code | Meaning |
|---|---|
| `3` | 401/403 — token missing/expired, or the `groups` claim isn't authorized |
| `4` | 404 — endpoint not found |

## See also

- [Configuration](configuration.md) — contexts, env vars, global options.
- [CLI reference](reference/cli.md) — `token set`, `whoami`, `login`.
