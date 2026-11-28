---
title: Flow assistant for visual ETL
description: "Configure a bring-your-own-key AI assistant for Ciaren. Build CSV flows, diagnose joins, check the canvas and safely revert saved changes."
search: flow assistant BYOK CSV ETL Join diagnose activity history revert
---

# Flow assistant for visual ETL

Open a flow and choose **Assistant**. You can check the canvas or look up the selected node immediately. To generate a proposal, choose a provider under **Settings → Assistant** and save the setting. Select a supported model, choose a reasoning effort if offered, and configure its API key. The assistant starts off. ChatGPT and Claude consumer subscriptions have separate billing from their APIs.

Follow [Set up the AI assistant and build a CSV flow](flow-assistant-quick-start.md) for a first run. To give an external agent a read-only catalog tool, see [Connect your own agent](external-agent.md).

## Walkthrough: recover a missing order

![The flow assistant highlights a Join and previews its repair, then shows the saved change and its reversal in Activity](/screenshots/flow-assistant-join.gif)

1. Order 104 has no matching SKU in the catalog. An inner Join drops that order even though the run succeeds. In **Diagnose**, ask to keep every order, including those without a catalog match.
2. Inspect the highlighted **Join / Merge**. The proposal changes `inner` to `left` and keeps the key and both inputs. Choose **Apply and save** when the preview matches your intent. Use **Run** separately to regenerate the CSV.
3. Open **Activity**, expand **Saved repair**, and select **Preview reversal**. The inverse shows `left → inner`. **Confirm reversal** adds an entry and preserves a later, unrelated sort edit. The next run uses the restored Join.

The recording uses the packaged editor, the synthetic orders audit and a simulated provider response. The canvas, validation, saves and history use the real application.

## Inside the editor

- **Build or modify a flow.** On an empty canvas choose an uploaded dataset from the current project. On an existing file flow the assistant uses its input and pinned version. Describe the result you want in your own words, in any language, for example “join orders with customers, compute revenue per country and chart it” or “train a random forest with 5-fold cross validation and show feature importance.” Review the nodes, configuration and connections. **Apply and save** saves the proposal and any unsaved canvas edits together. Undo restores the earlier canvas as a local edit. Save it to persist the undo.
- **Ask the Ciaren guides.** Ask a question about the editor, exports, parameters, scheduling or another bundled guide. The server searches the local English-language index. The selected passage links to its exact Git revision and line. An unsupported question can return no matching passage.
- **Diagnose a failure.** The server checks this flow's most recent failed run, categorizes the error locally and passes the category and graph structure to the selected model. A proposed repair goes through the same review and save path. Check an old failure against the current canvas before applying it.

A request keeps running while the panel is closed, and the **Assistant** button shows a dot when the reply is ready. The progress line names the current step, such as reading a schema or checking the flow. **Cancel** stops the request and closes the provider connection, and so does leaving the flow. A provider can still bill work already performed. A saved-flow revision conflict, changed input version or expired proposal requires a new proposal. Reload the editor after a concurrent save, preserving any local work first. A reply can end with buttons for a likely next step, such as saving, sharing column names or opening a guide.

## What the assistant can build

With OpenAI, Anthropic or DeepSeek the assistant works step by step through server-side tools. It looks up node settings in the installed catalog, reads the column types of the selected datasets, proposes edits and checks the result before it shows you a proposal. When a check fails, it reads the issue and corrects its own edit. You see one proposal per request.

It can use these built-in nodes:

| Area | Nodes |
| --- | --- |
| Inputs and outputs | File Input and File Output; existing format-specific inputs stay readable |
| Rows | Filter, Sort, Limit, Sample, Remove Duplicates, Drop or Fill Nulls, Remove Outliers, Explode |
| Columns | Select, Drop, Rename, Cast, Combine, Coalesce, Replace or Map Values, String Transform, Split, Round, Bin, Conditional Column, date parts, date parsing and date difference |
| Combine and reshape | Join, Concatenate, Group By, Pivot, Unpivot, Window, Rolling Aggregate, Row Difference |
| Data quality | Assert Not Null, Unique, Value Range, Row Count and Values in Set |
| Charts | Bar, Line, Area, Scatter, Pie, Histogram, Box Plot and Heatmap |
| Machine learning (ML extension) | Select Features, Scale, Encode, Reduce Dimensions, Train/Test Split, classifier and regressor models, training, clustering, Predict, Evaluate, Feature Importance and Cross Validate |

Filter Expression, Calculated Column and Assert Expression accept a short arithmetic or comparison expression such as `price * qty > 100`. The server allows only column references, numbers, single-quoted text, comparison and arithmetic operators and the functions `abs`, `sqrt`, `exp`, `log10`, `log1p`, `sin`, `cos`, `floor` and `ceil`. The proposal highlights these nodes so you can read the expression before saving.

The assistant never writes Python Transform nodes, database or cloud storage connectors, format-specific outputs, forecasting models or plugin nodes. It cannot change connections, credentials or file paths. Model settings are limited to the documented hyperparameters with upper bounds, for example at most 500 trees. A request that needs anything else ends with an explanation instead of a partial flow. Add those nodes in the editor.

The checks run on placeholder rows: each input keeps its column names, types, row count (up to 200 rows), distinct-value counts and whether a column has nulls, but every value is generated. Types and wiring are checked before you see the proposal. A value-dependent failure, such as text that does not parse as a date, appears when you run the flow, and **Diagnose** can propose a repair. Columns named after values, such as one-hot or pivot columns, have generated names in these checks, so the assistant cannot select them by name; a model node then uses every column except the target.

Column names stay on the server unless you share them. When a request names columns that the types cannot identify, the assistant asks instead of guessing, and the reply offers **Share column names and retry**.

The OpenCode adapter has no tool calling. It uses the guided proposals described below: the cleaning steps, the two-input Join and the shipping regression.

### Joining two CSV inputs

On an empty canvas select the left dataset, then the optional **Right input for Join**. Both CSVs must belong to the flow's project. They need one same-named key of the same type within the first 64 columns of each input and no other overlapping column names. Open **Data shared with provider** and choose **Include column names in this request** if the question refers to specific fields. Review the two filenames, versions, key, join mode, and left/right wiring before applying. Press **Run** separately to execute.

A proposed Join can keep matching rows (`inner`) or retain all left rows (`left`), add one boolean equality flag on a text column, sort ascending by one input column and write a CSV. For the repository's `examples/orders-audit`, choose orders on the left and catalog on the right. Ask to keep all orders by SKU, mark `ready_to_fulfill` when `catalog_status` equals `active`, and sort by `order_id`. The flag uses Ciaren's built-in Conditional Column. Duplicate keys can multiply rows. With null keys on both sides, pandas can match the nulls while Polars leaves them unmatched.

If an inner Join drops an unmatched order, describe the missing left rows under **Diagnose a failure**. For a supported existing canvas the only proposed edit is `how` from `inner` to `left`. Review and apply it, then rerun. Both input snapshots are checked atomically at confirmation. A newer version invalidates a selection that followed latest. An explicitly pinned input continues to use its exact immutable version. Joins with multiple keys, different key names, additional overlap or plugins can be edited manually.

## Train a shipping cost model from three CSVs

With the ML extension enabled, Build can generate two inner joins followed by a seeded train/test split, linear regression, held-out prediction, evaluation and a metrics CSV. This plan starts on an empty canvas. The first CSV supplies the numeric target, and each lookup contributes one numeric predictor. Identifiers used for joining cannot be training features or targets.

1. Upload `orders.csv`, `customers.csv` and `catalog.csv` from the [shipping regression example](https://github.com/ciaren-labs/Ciaren/tree/main/examples/shipping-regression) into the same project. Create a blank flow there.
2. Open **Assistant → Build**. Choose orders under **Input dataset**, customers under **Right input for Join** and catalog under **Second lookup for regression**. Select **shipping_cost** as the **Regression target**.
3. Open **Data shared with provider** and allow column names for this request. Ask: **Join orders to customers and catalog. Predict shipping cost from distance and weight with linear regression. Evaluate on held-out orders.** Choose **Create proposal**.
4. Check both Join keys (`customer_id`, then `sku`), the features (`distance_km`, `weight_kg`) and the target. Check that Split's **train** port feeds the regressor while **test** and the fitted **model** feed Predict. Choose **Apply and save** after review.
5. Choose **Run**. Select **File Output → Download output**. This synthetic example keeps 80 orders, trains on 64 and evaluates 16. The reference run has mean absolute error of about 0.27 currency units and R² of 0.997.

Each lookup must have exactly one compatible key in common with the first CSV. The lookups must have distinct column names from each other. Ciaren checks the saved profile for a unique, non-null key across the whole lookup. A sampled profile cannot establish uniqueness. Both joins keep matched rows. The run needs at least 13 matching orders with usable numeric targets. The provider receives no rows or key values, so the proposal cannot establish how many orders match. Review the run counts when using your own data.

The split uses seed 42 and holds out 20% of matched rows. Only the training branch fits the model. Choose features available at prediction time. Repeated measurements or historical forecasts can need a grouped or time-based split in a manually built flow. The three selected dataset versions and the flow revision are checked again before saving.

On **Run**, the existing training node logs the fitted model and up to five rows of feature values to the installation’s configured MLflow store. That store can be remote. The LLM receives only the request and temporary join, target and predictor references by default. Opting in shares column names for that turn. When a lookup has multiple numeric candidates, Ciaren requires the opt-in to distinguish them. The model cannot choose a tracking endpoint, model URI, arbitrary hyperparameters or executable code.

## Canvas tools and activity

Open **Assistant → Conversation**. **Build**, **Guides** and **Diagnose** choose the task. A proposed edit shows the affected nodes and wiring. Expand **Connections** to check the ports, or **Compare all settings** to inspect an existing node. **Inspect on canvas** returns to that node. The request and proposal stay in the open panel until you close it.

**Explain selected node** opens the selected node’s bundled guide. **Check canvas** applies the editor’s validation rules and links node-specific issues to their inspector. Both work locally without a provider. Only **Apply and save** commits an assistant proposal. Executing the flow requires the editor’s **Run** action.

**Assistant → Activity** lists confirmed changes for this flow, most recent first. Expand an entry to see node types, ports and fields, including the before and after for supported settings. Proposals, requests, provider responses, key material, rows and full graph snapshots are excluded. Activity starts with the first assistant save after upgrading. Run `ciaren db upgrade` on existing installations before starting the upgraded server. On MySQL and MariaDB the migration enables microsecond precision on flow revisions.

**Preview reversal** shows the inverse edit without changing the flow. **Confirm reversal** writes a new revision and links it to the original in the same database transaction. The original entry stays visible after reload. Toolbar **Undo** edits the current canvas in memory. Save or discard pending canvas edits before reverting a saved revision. Viewing activity and reversing a saved change work with the provider switched off.

Reversals preserve unrelated edits when the saved inverse can be proven safe. For example, reverting a Join mode keeps a later downstream sort. Ciaren checks the project, flow revision, affected settings, dependencies and bound inputs again when you confirm. If another client saves after a preview, preserve local work, reload and preview again. A changed dependency, a removed input, or a prior private value that cannot be reconstructed requires a manual edit. Reversals are final entries in the timeline; a fresh proposal can reapply a change.

The editor sends the loaded revision on **Save** and on the save before **Run**. Run creation checks the returned revision again before taking its execution snapshot. If you edit during a Run, the editor keeps the draft open and links to the result. A conflict leaves the draft on the canvas and offers a separate tab to compare the saved version. API callers can pass `expected_revision` (the flow’s `updated_at`) on both `PUT /api/flows/{id}` and `POST /api/flows/{id}/runs`. Older clients that omit it retain unconditional save and latest-version execution; upgrade those clients to protect their writes.

Access follows the installation’s existing server authentication. The timeline records the source of a change and the user’s confirmation without attributing it to a named person. A moved flow’s prior project entries are hidden. Activity pages contain up to 20 entries. Reversal previews use up to 64 short-lived process-local references with a three-minute timeout. Use sticky routing or a single process for confirmations. Deleting the flow deletes its activity.

## What leaves the server

Every request includes the text you enter. Keep credentials and confidential row values out of that text. Graph requests additionally include supported node types, indexed connections, column indexes and coarse types. For two-input creation, the provider receives temporary input and port references and the indexes of matching keys. A Join repair sends the question, a temporary Join reference, its current mode and, during diagnosis, a fixed error category. Opt in to column names for a single request when they matter. Documentation questions send up to five bundled passages without canvas context.

For a dataset the provider can receive the column types, the row count, and each column's null fraction and distinct count from the stored profile. Checks of a proposed node run on placeholder rows and send only column references, types and whether a column is numeric: no row values, counts or flags such as whether a result is empty. Because no check reads real values, its outcome cannot answer a guess about your data, for example whether a filter matches any row. Data-quality checks such as Assert Row Count pass their rows through in these checks and run when you run the flow.

Files, samples, filenames, dataset IDs, connection details, node labels, scripts, full configuration, raw logs and error traces stay on the server. Recommendations and citations are rendered as text. The assistant cannot run a pipeline. Review uses ordinary Ciaren nodes, so the existing run, export and undo controls continue to work.

## Deployment and credentials

Ciaren settings and provider credentials belong to one server instance. Anyone with access to its API can manage the assistant within the installation's token and browser-origin rules. Deploy separate instances, data directories and secret sources for separate trust boundaries. Use TLS and the Ciaren API token for a networked installation. Configure reverse proxies and monitoring to omit request bodies and authorization headers. Restrict process and diagnostic dump access at the operating-system level.

The settings page follows Ciaren's precedence for non-secret values. A saved override wins over the environment, followed by the built-in default. **Reset** removes that override. Use `CIAREN_ASSISTANT_PROVIDER` and provider-specific variables such as `CIAREN_ASSISTANT_OPENAI_MODEL` and `CIAREN_ASSISTANT_OPENAI_EFFORT`. Use the provider name in capitals for its model variable. Only OpenAI, Anthropic and DeepSeek expose an `_EFFORT` variable. OpenCode uses the provider default. The Settings page labels the effective value **Custom**, **From environment** or **Default**. For `CIAREN_ASSISTANT_PROVIDER` use `openai`, `anthropic`, `deepseek`, `opencode` or `off`. For a direct DeepSeek API key, select **DeepSeek** and `deepseek-flash`. An OpenCode Go credential belongs to OpenCode. This version’s OpenCode adapter has no DeepSeek model. Select **off** to stop assistant requests. Set `CIAREN_ASSISTANT_ENABLED=false` and restart to enforce this on the server.

To rotate a key stored in the native keyring, enter the replacement in **New API key** and choose **Save key**. **Remove key** deletes the stored credential. An environment or file source is administered on the server. Ciaren uses the configured source exclusively.

Select exactly one credential source per provider with `CIAREN_ASSISTANT_<PROVIDER>_KEY_SOURCE`.

| Source | Set, rotate or revoke |
| --- | --- |
| `keyring` (default) | Install `ciaren[keyring]` and use an unlocked native Windows, macOS or Secret Service backend. Use **Save key** to replace the key or **Remove key** to delete it. Entries use a separate service derived from the resolved data directory. An unsupported keychain reports unavailable. |
| `env` | Inject `CIAREN_ASSISTANT_<PROVIDER>_API_KEY` into the server process using a deployment secret. Restart after replacing or removing it. |
| `file` | Mount a read-only file named `openai`, `anthropic`, `deepseek` or `opencode` inside `CIAREN_ASSISTANT_SECRET_DIR` (default `/run/ciaren-assistant-secrets`). Files are read per request. Use a regular file, readable only by the service account. |

For Docker or a headless install, set the non-secret variables below and mount the selected secret file. Keep the source file outside the repository, build context, data directory and connector roots. Set `CIAREN_STORAGE_ALLOWED_ROOTS` to dedicated dataset folders on shared installations.

```yaml
services:
  ciaren:
    environment:
      CIAREN_ASSISTANT_PROVIDER: openai
      CIAREN_ASSISTANT_OPENAI_MODEL: gpt-5-mini
      CIAREN_ASSISTANT_OPENAI_EFFORT: low
      CIAREN_ASSISTANT_OPENAI_KEY_SOURCE: file
    volumes:
      - /srv/private/ciaren/openai:/run/ciaren-assistant-secrets/openai:ro
```

For the repository Compose setup, save the fragment as `docker-compose.override.yml` alongside `docker-compose.yml`. Set the host path to an existing secret file and recreate the service with `docker compose up -d --build ciaren`. For process injection, set `CIAREN_ASSISTANT_DEEPSEEK_KEY_SOURCE=env` and have your secret manager supply `CIAREN_ASSISTANT_DEEPSEEK_API_KEY` to the server process when using DeepSeek. Keep secrets out of shell history and committed environment files.

Revoke compromised keys in the provider console as well. Status checks do not contact the provider. A configured status indicates a local credential exists.

The server removes `CIAREN_ASSISTANT_*_API_KEY` variables from its environment at startup and from run worker processes, so flow code cannot read them there. A Python Transform node still runs with the server's privileges and can read a key that is in process memory or on disk. On a shared installation set `CIAREN_EXECUTION_MODE=process` and `CIAREN_PYTHON_TRANSFORM_STRICT=true`, prefer the `file` or `keyring` source, and allow only trusted users to edit flows. See [Advanced setup](advanced-setup.md).

## Provider contracts

| Provider | Allowed models | Effort in Ciaren | API family |
| --- | --- | --- | --- |
| OpenAI | `gpt-5-mini`, `gpt-5` | default, low, medium, high | Responses with storage disabled |
| Anthropic | `claude-sonnet-4-6` | default, low, medium, high | Messages, adaptive thinking for explicit efforts |
| DeepSeek | `deepseek-flash`, `deepseek-v4-pro` | default, none, low, high, max | Chat Completions, single turn |
| OpenCode Console | `minimax-m2.7`, `kimi-k2.6` | provider default | Paid OpenAI-compatible Chat Completions |

Default omits the effort field. Each provider has its own fixed HTTPS destination, model and credential. OpenCode's Console API routes vary by family and its free-tier chat models are restricted to OpenCode clients. Use an OpenCode Console API key for this adapter. Model availability, provider retention and charges depend on the selected provider and account. See [OpenAI reasoning](https://developers.openai.com/api/docs/guides/reasoning), [Anthropic thinking](https://platform.claude.com/docs/en/build-with-claude/extended-thinking), [DeepSeek thinking](https://api-docs.deepseek.com/guides/thinking_mode/) and [OpenCode Console inference](https://opencode.ai/docs/console/api/inference).

## Bounds and implementation

Input is limited to 1,500 request characters, 80 canvas nodes, 160 edges and 64 columns per source. One turn makes at most 14 provider calls and 40 tool calls within 120 seconds; each provider call has a 35-second timeout and 2,048 output tokens, and each tool call 15 seconds. The opening request is at most 12 KB, and older tool results are compacted to keep the conversation under 96 KB. One edit applies up to 24 operations. Each check previews at most 50,000 rows and 2 million cells per node within 15 seconds; a single slow node step can overrun that deadline. Up to eight turns may be active per process, one per flow. Up to 64 proposals live in memory for three minutes. Use a single process or sticky routing for proposal confirmation.

Each application process allows 60 provider calls per rolling hour by default (`CIAREN_ASSISTANT_TURNS_PER_HOUR`). The limit counts calls, not turns: a turn reserves its calls when it starts and returns the unused ones when it ends. Set `CIAREN_ASSISTANT_TOKENS_PER_HOUR` to also cap tokens. Configure provider-side spend limits for a currency-denominated cap. Requests use zero automatic retries. If a turn reaches its call limit, the assistant validates the latest draft and returns it when it passes. The UI renders a change only after the server has validated it.

The tools run inside the Ciaren server against the installed node registry and the same validation as the editor. The model receives turn-local references (`d0` for datasets, `n0` for nodes, `c0` for columns), never dataset IDs, file paths or rows. Every edit passes an allowlist of node types and settings before anything runs, and nothing is saved until you choose **Apply and save**. Plugin, code and connector flows receive read-only diagnostic recommendations based on node types, wiring and the failure category. Edit those graphs in the regular editor.

The assistant has no shell, generic network or file tools, direct repository access or arbitrary code generation, and Ciaren runs no MCP listener for it. The tools already run in-process with the editor's session and checks; an MCP transport would add a second credential and authorization boundary without giving the assistant new abilities. To drive Ciaren from your own agent, see [Connect your own agent](external-agent.md). The two local canvas tools reuse existing documentation and validation. The activity endpoint handles confirmed edits separately from model tools and never provides history to the model.
