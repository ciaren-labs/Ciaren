---
title: Local-First Trust Model
description: What FlowFrame trusts, what it does not, and where the boundaries are
search: security trust model local-first sandbox permissions secrets
---

# Local-First Trust Model

FlowFrame runs on **your** machine and executes **your** pipelines against **your**
data. That shapes the security model: the primary trust boundary is "code and data
you chose to run," not a multi-tenant server.

## What FlowFrame assumes

- A single, trusted local user operates the app.
- The user owns the data, the database, and the execution environment.
- No FlowFrame-hosted service is required to run pipelines.

Under those assumptions some power-user features (custom Python nodes, custom SQL)
are intentionally available. They run with the privileges of the local process.

## What is *not* a hard boundary

- **Plugins and `pythonTransform` are not sandboxed.** Python code a plugin or a
  custom node runs has the same access as the FlowFrame process. The
  [permission model](/security/plugin-security) is a *trust and consent* boundary
  (what loads, after you approve it), not an OS-level sandbox.
- **Local license checks are not unbreakable DRM.** They deter casual misuse of
  premium plugins; a determined user can bypass them.
- **Signatures prove integrity and origin, not safety.** A validly signed plugin
  can still be poorly written; signing only proves it wasn't tampered with and came
  from a key you trust.

## Where FlowFrame *does* enforce boundaries

- **Secrets stay out of artifacts.** Connection passwords are referenced by
  environment-variable name (`password_env`), never stored in the flow graph,
  `.flow` documents, or generated code — exported scripts read the secret from
  `os.environ` at run time.
- **Model loading refuses code execution.** Pickle (`.pkl`/`.pickle`) model files
  are refused because loading a pickle runs arbitrary code; only `.joblib` and
  native `.json` model artifacts inside the artifact root load. See
  `app/ml/security.py`.
- **Model URIs can't escape the artifact root.** A local `model_uri` must resolve
  inside the configured artifact directory (no `..` traversal, no absolute paths
  elsewhere); otherwise an MLflow `runs:/` / `models:/` URI is required.
- **Plugin code is gated before import.** A drop-in plugin that declares
  permissions is not imported until you approve it.
- **Tampered packages are refused.** A `.ffplugin` whose contents don't match its
  signature digest never installs.

## Hardening for shared / team use (future)

The current model is tuned for local use. Before multi-user, team, or enterprise
deployments, add: read-only SQL connection modes, query allow/deny lists and
audit logs, per-plugin OS sandboxing, and admin-enforced permission policies.
These are deliberately out of scope for the local-first core.

## See also

- [Plugin security & permissions](/security/plugin-security)
- [Packaging & Distribution](/plugins/packaging-and-distribution)
