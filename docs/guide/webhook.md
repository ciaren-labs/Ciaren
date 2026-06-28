---
title: Webhook Trigger
description: Trigger FlowFrame flows from CI/CD pipelines, Airflow DAGs, and any HTTP client
search: webhook trigger secret ci cd airflow pipeline http external automation
---

# Webhook Trigger

FlowFrame exposes a `POST /api/flows/{id}/trigger` endpoint that lets any
HTTP-capable system start a run with a single request — no knowledge of the full
REST API needed. Access is controlled by a pre-shared secret.

## Configuration

Set `FLOWFRAME_WEBHOOK_SECRET` to any non-empty string before starting the server:

```bash
# .env file (recommended)
FLOWFRAME_WEBHOOK_SECRET=my-strong-secret-here
```

or inline:

```bash
FLOWFRAME_WEBHOOK_SECRET=my-strong-secret-here flowframe serve
```

When the variable is unset the trigger endpoint returns **404** — there is no
open trigger surface on a fresh install.

::: tip Generating a strong secret
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```
:::

## Checking whether the webhook is active

```bash
curl http://localhost:8055/api/settings/webhook
# → {"configured": true}
```

The response never includes the secret itself.

## Triggering a run

Send a `POST` to `/api/flows/{flow_id}/trigger` with the secret in the
`X-FlowFrame-Secret` header. The body is optional.

```bash
curl -X POST http://localhost:8055/api/flows/FLOW_ID/trigger \
  -H "X-FlowFrame-Secret: my-strong-secret-here" \
  -H "Content-Type: application/json"
```

The endpoint **blocks until the run completes** and returns the full run object:

```json
{
  "id": "run-abc123",
  "flow_id": "FLOW_ID",
  "status": "success",
  "trigger": "webhook",
  "engine": "polars",
  "started_at": "2026-06-25T14:00:01",
  "finished_at": "2026-06-25T14:00:03",
  "output_location": "run-abc123/out1.csv",
  ...
}
```

Check `status` to know whether the run succeeded (`"success"`) or failed
(`"failed"`). On failure, `error_message` contains the reason.

## Passing options

```bash
curl -X POST http://localhost:8055/api/flows/FLOW_ID/trigger \
  -H "X-FlowFrame-Secret: my-strong-secret-here" \
  -H "Content-Type: application/json" \
  -d '{
    "engine": "pandas",
    "parameters": { "date": "2026-06-25", "limit": 5000 }
  }'
```

| Field | Type | Description |
| --- | --- | --- |
| `engine` | `"polars"` \| `"pandas"` | Engine override for this run |
| `parameters` | object | [Flow-parameter](/guide/parameters) overrides (`name → value`) |

## Error responses

| Status | Reason |
| --- | --- |
| `404` | `FLOWFRAME_WEBHOOK_SECRET` is not configured |
| `403` | Header missing or value does not match the configured secret |
| `404` | Flow ID not found |

## GitHub Actions example

```yaml
- name: Trigger FlowFrame pipeline
  run: |
    curl -f -X POST ${{ vars.FLOWFRAME_URL }}/api/flows/${{ vars.FLOW_ID }}/trigger \
      -H "X-FlowFrame-Secret: ${{ secrets.FLOWFRAME_WEBHOOK_SECRET }}" \
      -H "Content-Type: application/json"
```

Store the server URL and flow ID as Actions variables, the secret as an Actions
secret.

## Airflow example

```python
from airflow.providers.http.operators.http import SimpleHttpOperator

trigger = SimpleHttpOperator(
    task_id="trigger_flowframe",
    method="POST",
    http_conn_id="flowframe_server",           # configured in Airflow connections
    endpoint=f"/api/flows/{FLOW_ID}/trigger",
    headers={"X-FlowFrame-Secret": "{{ var.value.flowframe_webhook_secret }}"},
    response_check=lambda r: r.json()["status"] == "success",
)
```

## Security notes

- The secret is compared with `hmac.compare_digest` to prevent timing attacks.
- Use HTTPS in production so the secret is never sent in plain text.
- Rotate the secret by updating `FLOWFRAME_WEBHOOK_SECRET` and restarting the
  server — all callers must update their copy simultaneously.

## See also

- [Python SDK](/guide/sdk) — a typed Python client wrapping this endpoint
- [Scheduling](/guide/scheduling) — cron-based triggers that don't need a caller
- [REST API: Runs](/api/runs) — the full runs API
