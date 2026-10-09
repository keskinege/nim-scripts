# nim-scripts

Scripts and tools for working with **F5 NGINX Instance Manager (NIM)** and
**F5 WAF for NGINX (v5)** policies, including conversion to Kubernetes PLM resources.

## Repository layout

```
nim-scripts/
├── README.md                     # this file
├── nimctl/                       # nimctl: Python CLI for the NIM REST API
│   ├── src/nimctl/               #   package source (commands/, http.py, oidc.py, ...)
│   ├── tests/                    #   pytest suite + JSON fixtures
│   ├── scripts/
│   │   ├── kc-token.sh           #   get a Keycloak token without leaking secrets
│   │   └── gen_command_reference.py  # generate docs/reference/cli.md from the CLI
│   ├── docs/                     #   MkDocs source (getting started, auth, reference)
│   ├── site/                     #   built MkDocs output (generated, do not edit)
│   ├── entry.py                  #   PyInstaller entry point
│   ├── Makefile                  #   test, lint, build-exe, docs targets
│   └── pyproject.toml            #   package metadata (Python 3.11+)
└── v5-json-to-manifest/          # v52plm.py: v5 JSON <-> PLM (APPolicy etc.) converter
    ├── v52plm.py                 #   the converter (single file)
    ├── pyproject.toml            #   dependency: PyYAML (Python 3.13+)
    └── uv.lock
```

## Scripts

### `nimctl` — NIM command-line client

`nimctl` authenticates to a NIM instance and drives it through the documented
`/api/platform/<version>` REST API. It provides typed commands for systems, instances,
configs, scans, metrics, security policies, certificates, users and more, plus a raw
`api call` passthrough for anything without a dedicated command.

Highlights:

- Settings resolve as **flag → environment variable → stored context → default**.
- Output as `json` (default), `raw` or `table`.
- Typed exit codes (`0` success, `3` auth, `4` not found, `5` conflict, `6` server error, ...).
- Basic auth or Bearer tokens, including OIDC login (`login-oidc --flow code|device`).
- A per-host OpenAPI spec cache under `$XDG_CACHE_HOME/nimctl/`.

Quick start:

```bash
cd nimctl
uv sync                                   # create the env and install dependencies
uv run nimctl context set host https://nim.example.com
uv run nimctl context set user admin
uv run nimctl context set password_file ~/.config/nimctl/admin.pw
uv run nimctl login
uv run nimctl systems list --output table
```

Build a single-file binary with `make build-exe` (outputs `dist/nimctl`).

Full documentation is in [`nimctl/README.md`](nimctl/README.md) and the MkDocs site
sources under [`nimctl/docs/`](nimctl/docs/). Run `make docs` to regenerate the CLI
reference and rebuild the site.


### `v5-json-to-manifest/v52plm.py` — WAF v5 JSON ⇄ PLM CRD converter

WAF v5 and PLM (Policy Lifecycle Management) share the same declarative policy language.
The only difference is packaging: plain JSON files versus Kubernetes custom resources.
`v52plm.py` wraps the JSON in a Kubernetes envelope (`apiVersion`/`kind`/`metadata`/`spec`)
and back. No policy setting is added, removed or renamed.

Supported kinds, detected from the top-level JSON keys:

| Input JSON | Top-level key | CRD kind |
|---|---|---|
| policy | `policy` | `APPolicy` |
| log profile | `filter` / `content` | `APLogConf` |
| user signatures | `signatures` | `APUserSig` |

Subcommands:

| Command | What it does |
|---|---|
| `to-crd` | JSON → CRD YAML. Prints to stdout, or writes files with `-o DIR`. |
| `to-json` | CRD YAML → JSON. Skips documents of other kinds. |
| `check` | Runs the full conversion and verification but writes nothing. Useful as a CI lint step. |

Useful options: `-n/--namespace`, `--name`, `--kind`, `--api-version`
(`appprotect.f5.com/v1` by default, `appprotect.f5.com/v1beta1` for NIC + WAF v4),
`-l KEY=VALUE` labels, `-f/--force` to overwrite, `--no-fix` to reject trailing commas.

Every conversion is **verified**: the output is parsed back and compared setting by
setting (keys, values and types) with the input. Any difference fails the run.
Trailing commas in hand-edited JSON are fixed automatically and reported.

Examples:

```bash
CONV="uv run --no-project --with pyyaml python v5-json-to-manifest/v52plm.py"

$CONV to-crd policy.json -n security -o plm/           # -> plm/<name>-appolicy.yaml
$CONV to-json plm/demo-appolicy.yaml -o json/          # -> json/demo.json
$CONV check policies/                                  # validate a directory only
```

Pipe NIM → cluster without intermediate files:

```bash
nimctl security policies get <policy_uid> --decode \
  | $CONV to-crd - -n security \
  | kubectl apply -f -
```

Exit codes: `0` if every file converted and verified, `1` if any file failed.

## Requirements

| Tool | Used by | Version |
|---|---|---|
| Python | nimctl | 3.11+ |
| Python | v52plm.py | 3.13+ (per `pyproject.toml`; the script itself needs 3.8+) |
| [uv](https://docs.astral.sh/uv/) | nimctl, v52plm.py | any recent |
| Bash, `curl`, `python3` | `kc-token.sh` | — |
| `kubectl` | applying converted manifests | optional |

## Important


- `nimctl/site/` and `nimctl/build/`, `nimctl/dist/` are generated output and should not be
  edited by hand.
