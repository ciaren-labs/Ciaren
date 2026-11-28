---
title: Troubleshooting Guide
description: "Fix Ciaren setup and runtime errors: database URLs, occupied ports, CORS, AI assistant keys and replies, missing modules, pandas exports, Windows paths and MLflow tracking."
search: troubleshooting help issues database cors port modules pandas export split assistant api key keychain provider
---

# Troubleshooting Guide

Common issues when running Ciaren. For broader questions, see the [FAQ](/faq).

:::tip
Run `ciaren check` to validate your environment in one shot — it reports a
non-writable data dir, a non-async database URL, an unreachable database, and the
available engines.
:::

## Database connection fails

Ciaren uses async SQLAlchemy. A plain `sqlite://`, `postgresql://`, or
`mysql://` URL will not connect. Use the async variant in
`CIAREN_DATABASE_URL`:

- `sqlite+aiosqlite:///./ciaren.db` (default)
- `postgresql+asyncpg://user:pass@host/db`
- `mysql+aiomysql://user:pass@host/db`

Install the matching driver (`asyncpg`, `aiomysql`) for non-SQLite databases.
Missing tables are created automatically on startup. After upgrading Ciaren,
run `ciaren db upgrade` against an existing database to apply changes to
tables that already exist. It is safe to re-run; see the
[CLI reference](/guide/cli#ciaren-db).

## "Port 8055 already in use"

Start the server on another port:

```bash
ciaren serve --port 8001
```

## Frontend can't reach the backend

The dev server proxies `/api` to `http://localhost:8055` by default. If your
backend runs elsewhere, point the proxy at it:

```bash
VITE_API_TARGET=http://localhost:8001 npm run dev
```

If the frontend port `5173` is taken, change it with `VITE_PORT=3000 npm run dev`
— and remember to add the new origin to `CIAREN_CORS_ORIGINS`.

## A scheduled flow stopped running

A schedule is **auto-disabled** after several consecutive failed runs (default 5),
with a `disabled_reason`. Re-enable it to clear the streak. Manual *run-now* stays
out of the retry/auto-disable machinery. See [Scheduling](/guide/scheduling).

## CORS errors

Add the calling origin to `CIAREN_CORS_ORIGINS` (a JSON list) in
`backend/.env`:

```
CIAREN_CORS_ORIGINS=["http://localhost:5173"]
```

If API auth is enabled, browser clients can send either
`Authorization: Bearer <token>` or `X-Ciaren-Token: <token>`; both are allowed by
the API's CORS preflight handling.

## The assistant asks me to connect a provider

The flow assistant needs one enabled API key marked **In use**. Open
**Connections → Assistant API keys**, add a key or select an existing one, and
check that **Enabled** is on. Disabling or removing the key in use leaves none
selected, and Ciaren does not pick another for you. If the server is
configured through the environment instead, the key must be present and
`CIAREN_ASSISTANT_ENABLED` must not be `false`. The status check never
contacts the provider, so a configured key can still be rejected later.

## "Add API key" is disabled

Saved keys live in the OS keychain of the computer that runs Ciaren, so the
button is disabled, with a note, when Ciaren finds no supported keychain
(Windows Credential Manager, macOS Keychain or Secret Service). Install the
extra with `python -m pip install "ciaren[keyring]"` and unlock the keychain.
On a headless server or container, configure the key with an environment
variable or a mounted file instead, as described in
[Flow assistant: server-managed keys](/guide/flow-assistant#server-managed-keys).

## The assistant fails with a keychain or provider error

"The OS keychain is unavailable" means the keychain is locked or was removed;
unlock it and retry. "The assistant's API key is missing" means the keychain
entry or the server's key source no longer holds a key, so add it again.
"Provider returned HTTP 401" or "403" points to a rejected key, and other
`4xx` codes to the model name or quota. A model you typed must exist at the
provider and support tool calling. Ciaren never retries a provider call, so
choose **Regenerate** to try again.

## "Save your changes first" or "Proposal expired"

The assistant reads the saved flow, never the unsaved canvas. Choose **Save
and send**, or save the canvas and send the request again. A proposal expires
three minutes after it appears and cannot be applied if the flow, one of its
input versions changed or the assistant was turned off in the meantime. Generate a
new proposal. If another tab saved the flow, reload the editor and keep your
local work first.

## "This model cannot edit flows" or a request is declined

Charts, machine learning and most multi-step flows need a model with tool
calling. OpenAI, Anthropic and DeepSeek models in the list qualify. The OpenCode
models in the list do not, and use a smaller set of guided plans. Choose another
key in **Connections**. Other replies are explanations, not errors: **The
assistant was not confident** asks for a more specific request, **The proposal
did not pass checks** means a draft failed validation and nothing was proposed,
and **Too many steps for one request** means you should split the request into
smaller changes. A draft marked **this draft was not checked** ran out of
steps, time or provider connection, so review it with extra care.

## "Request budget used up"

Each application process allows 60 provider calls per rolling hour by default,
and one complex Build can use up to 14. Wait for the window to pass, or raise
`CIAREN_ASSISTANT_TURNS_PER_HOUR` and restart. "Another assistant turn is
active" appears when eight requests are already running in the process, or the
same request is repeated; wait a moment and send it again.

## Diagnose says there is no failed run

Diagnose explains the latest failed run of the flow. When a run succeeded but
the result is wrong, such as rows missing after a Join, describe the change you
want in **Build** instead. Diagnose proposes a fix only for an inner Join that
drops left rows and for simple cleaning flows. For other failures it gives
advice and asks for a manual edit.

## Upload rejected as too large

The default upload limit is 100 MB. Raise it with
`CIAREN_MAX_UPLOAD_SIZE_MB` in `backend/.env`.

## Module not found errors

Activate the environment you use to run Ciaren, then check whether the package
is installed in that interpreter:

```bash
python -m pip show ciaren
```

For a PyPI installation, run `python -m pip install ciaren` in that environment.
For a source checkout, run `python -m pip install -e .` from the `backend/`
directory instead. Using `python -m pip` keeps installation tied to the selected
interpreter; a bare `pip` command can belong to a different environment.

For optional connector drivers, check the extras listed in
[Installation](./installation.md#recommended-pypi-package) and
[Connections](./connections.md). For an async database driver such as `aiomysql`,
follow [Database connection fails](#database-connection-fails) above instead;
the `mysql` connector extra installs `pymysql`, not `aiomysql`. Reinstalling the
base package does not add every optional driver. You do not need to delete your
existing virtual environment.

## Exported pandas code fails after Split column

**Symptom:** the flow runs in Ciaren, but an older exported pandas script fails
with `KeyError: 1` at `_parts[1]`. For example, splitting `['EU', None]` on `|`
into `region` and `city` produces no second field in any row.

**Cause:** pandas only creates split columns that exist in the data. An older
export can index a column that was never created, while Ciaren's runtime leaves
missing fields null.

**Workaround:** check each split column before assigning it and use `pd.NA` for
a missing output. For the example above:

```python
import pandas as pd

df_1 = pd.DataFrame({"location": ["EU", None]})
_parts = df_1['location'].astype('string').str.split('|', expand=True)
df_2 = df_1.assign(
    region=(_parts[0] if 0 in _parts.columns else pd.NA),
    city=(_parts[1] if 1 in _parts.columns else pd.NA),
)
```

The result keeps `region` as `['EU', null]` and `city` as `[null, null]`. Apply
the same check to each additional output; do not drop rows to avoid the error.
If your export already includes these checks, missing trailing fields are
expected nulls rather than an error. See the
[Split column reference](../transformations/split-column.md) and the
[split-column recipe](../recipes/split-a-column.md) for configuration and examples.

## Install fails on Windows with a long-path error

A `pip install` can fail on Windows with an error like
`OSError: [Errno 2] No such file or directory: '...\mlflow\store\db_migrations\versions\...'`
and a hint about enabling *long-path support*. Ciaren bundles MLflow, whose
internal file paths are long, so installing into a deeply nested folder can push
the full path past Windows' legacy 260-character limit.

Fix it either way:

- **Enable long paths (recommended, one-time).** In an Administrator PowerShell:

  ```powershell
  Set-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem' LongPathsEnabled 1
  ```

  Reopen your terminal, then reinstall. See the
  [pip long-paths note](https://pip.pypa.io/warnings/enable-long-paths).
- **Or install into a shorter path** — create the virtual environment close to
  the drive root (for example `C:\ciaren\.venv`) instead of a deeply nested
  directory.

## ML training succeeds but the model isn't tracked (Windows)

A training run finishes **green**, its metrics show up, but the node's **model
URI** and **MLflow run id** are blank — and a downstream **Predict** or **Feature
Importance** node then fails because there's no model to load. The server log
shows a warning like:

```
mlTrainClassifier: MLflow logging failed ([WinError 206] The filename or extension
is too long: '...\mlruns\...\models\...') — model trained but not tracked.
```

This is the same Windows 260-character path limit as the install error above, but
at **run time**: MLflow writes artifacts under your tracking directory
(`CIAREN_MLFLOW_TRACKING_URI`, default `./mlruns` inside the working directory),
and its nested `mlruns/<exp>/<run>/models/...` layout can push the full path over
the limit when Ciaren runs from a deeply nested folder. Training itself is
in-memory, so it still succeeds — only the logging step fails, which is why the
run is green but untracked.

`ciaren check` catches this ahead of time: when the tracking store is a local
folder and long paths are off, it prints an `ml_path` line — `[warn]` (with the
fix) if the path is long enough to be at risk, `[ok]` otherwise.

Fix it either way:

- **Enable long paths** (recommended, one-time) — the same
  `LongPathsEnabled` registry setting shown in the install section above.
- **Point the tracking store somewhere short** — set an absolute, shallow
  `CIAREN_MLFLOW_TRACKING_URI` (for example `CIAREN_MLFLOW_TRACKING_URI=C:\mlruns`),
  or run Ciaren from a directory close to the drive root. You can also edit the
  **Local MLflow** connection's Tracking URI in the **Connections** page.

## Still stuck?

- [Installation Guide](/guide/installation)
- [FAQ](/faq)
- [GitHub Issues](https://github.com/ciaren-labs/Ciaren/issues)
