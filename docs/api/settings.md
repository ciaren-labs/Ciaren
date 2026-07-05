---
title: Settings API
description: Read and override the runtime-editable server settings
search: api settings runtime configuration override reset env default engine timeout upload retention scheduler webhook
---

# Settings API

Backs the Settings page: a small, explicitly allowlisted subset of the server's
configuration can be read and overridden at runtime. Overrides are stored in
Ciaren's database, applied to the running server immediately, and re-applied on
every startup — so they take precedence over environment variables until reset.
See [Advanced Setup](/guide/advanced-setup#the-settings-page) for which
settings are editable and why the rest are environment-only.

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/settings` | List every editable setting with metadata and its effective value |
| `PUT` | `/api/settings/{key}` | Set an override: `{"value": …}` |
| `DELETE` | `/api/settings/{key}` | Remove the override, falling back to env/default (idempotent) |

Each item carries the UI metadata and current state:

```json
{
  "key": "MAX_UPLOAD_SIZE_MB",
  "env_var": "CIAREN_MAX_UPLOAD_SIZE_MB",
  "label": "Max upload size (MB)",
  "description": "Largest dataset file the upload endpoint accepts.",
  "category": "Datasets",
  "value_type": "integer",
  "choices": null,
  "min_value": 1,
  "max_value": 10240,
  "restart_required": false,
  "value": 250,
  "source": "override",
  "default_value": 100,
  "env_value": 100
}
```

- `value` is the **effective** value; `source` says where it comes from
  (`override` > `env` > `default`).
- `env_value` is what a `DELETE` would restore (the environment variable if
  set, else the built-in default).
- `env_var` names the environment variable the setting maps to. While an
  override exists, editing that variable has **no effect** — the override wins
  until it is deleted.
- `value_type` is `integer` (with `min_value`/`max_value`), `select` (with
  `choices`), or `url` (http/https, empty string to disable; no current
  setting uses it).
- `restart_required: true` marks values consumed once at startup (e.g.
  `SCHEDULER_MAX_CONCURRENT_RUNS` sizes the worker pool); the override is
  saved immediately but only fully applies after a restart.

Writes are validated server-side: an unknown or non-editable key (secrets,
security guards, bootstrap values) is a `404`; a value of the wrong type, out
of range, or not among `choices` is a `400` and changes nothing. Values never
include secrets — the editable set contains none by design.

Like the rest of `/api`, these endpoints honour the optional
[`CIAREN_API_TOKEN`](/guide/advanced-setup#production-deployment) gate and the
browser-origin (CSRF) guard.
