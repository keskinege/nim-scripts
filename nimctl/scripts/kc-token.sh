#!/usr/bin/env bash
# kc-token.sh — obtain a Keycloak access token for NIM without leaking secrets.
#
# Secrets never appear on a command line (so they never reach shell history or
# `ps`): they are read from 0600 files and handed to curl with `name@file`, so
# only a file PATH is ever in argv.
#
# Config file (default: ~/.config/nimctl/kc.env), chmod 600:
#
#   KC_TOKEN_ENDPOINT=https://keycloak.tail7fa79.ts.net/auth/realms/my-realm/protocol/openid-connect/token
#   KC_CLIENT_ID=cliapp
#   KC_CLIENT_SECRET_FILE=/home/you/.config/nimctl/cliapp.secret   # preferred
#   # KC_CLIENT_SECRET=...        # inline is accepted but a 0600 file is better
#   KC_USERNAME=alice
#   KC_PASSWORD_FILE=/home/you/.config/nimctl/alice.pw             # preferred
#   # KC_PASSWORD=...
#   KC_INSECURE=1                 # if Keycloak's cert is self-signed
#
# Usage:
#   scripts/kc-token.sh                  # password grant -> token.jwt (0600)
#   scripts/kc-token.sh --refresh        # refresh_token grant -> token.jwt
#   KC_CONFIG=/path/to/kc.env scripts/kc-token.sh -o /path/token.jwt
set -euo pipefail

CONFIG="${KC_CONFIG:-$HOME/.config/nimctl/kc.env}"
OUT="token.jwt"
REFRESH=false
TOKEN_FILE="$HOME/.config/nimctl/nim.token"

while [[ $# -gt 0 ]]; do
  case "$1" in
    -c|--config)  CONFIG="$2"; shift 2 ;;
    -o|--out)     OUT="$2"; shift 2 ;;
    --refresh)    REFRESH=true; shift ;;
    --token-file) TOKEN_FILE="$2"; shift 2 ;;
    -h|--help)    sed -n '2,27p' "$0"; exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

[[ -f "$CONFIG" ]] || { echo "config not found: $CONFIG (chmod 600)" >&2; exit 1; }
perm="$(stat -f '%Lp' "$CONFIG" 2>/dev/null || stat -c '%a' "$CONFIG")"
[[ "$perm" == "600" ]] || echo "warning: $CONFIG is mode $perm; run: chmod 600 '$CONFIG'" >&2

# shellcheck disable=SC1090
set -a; . "$CONFIG"; set +a

umask 077
TMPDIR_KC="$(mktemp -d)"; trap 'rm -rf "$TMPDIR_KC"' EXIT

# Normalize a secret value to an exact 0600 file with no trailing newline, so it
# can be passed to curl as `name@file` (value stays out of argv).
file_for() {
  local f
  f="$(mktemp "$TMPDIR_KC/secret.XXXXXX")"
  printf '%s' "$1" > "$f"
  chmod 600 "$f"
  printf '%s' "$f"
}
# Resolve a secret from a file or an inline value into a temp file; empty -> nothing.
secret_arg() {  # $1=file path, $2=inline value, $3=field name ; echoes curl arg
  local val
  if [[ -n "${1:-}" ]]; then val="$(cat "$1")"; else val="${2:-}"; fi
  [[ -n "$val" ]] || return 0
  printf '%s@%s' "$3" "$(file_for "$val")"
}

CURL=(curl -fsS)
[[ "${KC_INSECURE:-}" == "1" ]] && CURL+=(-k)

args=(--data-urlencode "client_id=${KC_CLIENT_ID}")

if [[ "$REFRESH" == true ]]; then
  [[ -f "$TOKEN_FILE" ]] || { echo "no refresh token at $TOKEN_FILE" >&2; exit 1; }
  args+=(--data-urlencode "grant_type=refresh_token")
  args+=(--data-urlencode "refresh_token@$(file_for "$(cat "$TOKEN_FILE")")")
else
  args+=(--data-urlencode "grant_type=password")
  args+=(--data-urlencode "username=${KC_USERNAME}")
  pw_arg="$(secret_arg "${KC_PASSWORD_FILE:-}" "${KC_PASSWORD:-}" password)"
  [[ -n "$pw_arg" ]] && args+=(--data-urlencode "$pw_arg")
  args+=(--data-urlencode "scope=openid profile email")
fi
cs_arg="$(secret_arg "${KC_CLIENT_SECRET_FILE:-}" "${KC_CLIENT_SECRET:-}" client_secret)"
[[ -n "$cs_arg" ]] && args+=(--data-urlencode "$cs_arg")

resp="$("${CURL[@]}" -X POST "$KC_TOKEN_ENDPOINT" \
  -H 'Content-Type: application/x-www-form-urlencoded' "${args[@]}")"

# Never echo the secret or the raw response; only write files.
printf '%s' "$resp" | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])' > "$OUT"
printf '%s' "$resp" | python3 -c 'import sys,json; print(json.load(sys.stdin).get("refresh_token",""))' > "$TOKEN_FILE"
chmod 600 "$OUT" "$TOKEN_FILE"
echo "wrote $OUT and $TOKEN_FILE (access + refresh)"
