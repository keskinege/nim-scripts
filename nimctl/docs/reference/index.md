---
title: Reference
---

# Reference

- **[CLI reference](cli.md)** — every command, argument and option, generated from the
  live Typer app.
- **[Configuration](../configuration.md)** — contexts, environment variables and global
  options.

## NIM API coverage

`nimctl` wraps the common NIM operations directly and exposes everything else through
the `api` passthrough (`nimctl api call <METHOD> <path>`). NIM's OpenAPI document is
`/ui/manager.json`; inspect it with:

```bash
uv run nimctl api tags
uv run nimctl api paths <tag>
uv run nimctl api spec
```
