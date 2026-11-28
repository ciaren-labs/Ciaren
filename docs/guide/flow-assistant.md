---
title: Flow assistant for visual ETL
description: "Describe a data flow in plain language and review the nodes the Ciaren assistant proposes. Covers prompts, review, limits, privacy, API keys and activity history."
search: flow assistant AI natural language build flow BYOK API key privacy limits diagnose guides activity history revert
---

# Flow assistant for visual ETL

Describe the data flow you want in plain language. The assistant proposes the nodes, settings and connections for the canvas, checks the result and shows it to you for review. Nothing is saved until you choose **Apply and save**, nothing runs until you choose **Run**, and you can keep editing the flow by hand at any point.

The assistant is bring-your-own-key and starts off. Add a provider API key under **Connections → Assistant API keys** to turn it on. ChatGPT and Claude consumer subscriptions have separate billing from their APIs. It is an alpha feature: review every proposal, because the assistant's own checks confirm types and wiring, not that your data produces the result you want.

Follow [Set up the AI assistant and build a CSV flow](flow-assistant-quick-start.md) for a first run. To give an external agent a read-only catalog tool, see [Connect your own agent](external-agent.md).

## What you can ask for

With OpenAI, Anthropic, DeepSeek or a model you type that supports tool calling, Build works step by step. The assistant looks up node settings in the installed catalog, reads the column types of your datasets, drafts edits, checks the flow and corrects its own mistakes before it shows you one proposal. You can describe a whole pipeline in a single request, in any language, up to 1,500 characters.

These requests use only nodes the assistant can create. Replace the column names with your own.

- **Clean and validate.** “Drop rows where income is empty, fill missing age with the median, remove duplicate customer_id rows, check that customer_id is unique and write the result.”
- **Combine and aggregate.** “Join orders with customers on customer_id, calculate revenue as price times quantity, total revenue per country, sort it descending and show it as a bar chart.”
- **Dates and trends.** “Parse signup_date, extract the year and month, count signups per month and plot them as a line chart.”
- **Features and models** (ML extension). “Encode the categorical columns, scale the numeric ones, split 80/20, train a random forest classifier to predict churn, evaluate it and show feature importance.”
- **Change an existing flow.** “Keep every row from the left input in the Join”, or “add a filter for revenue above 100 before the Group By.”

The panel offers a few starting prompts under **Try**, based on the selected dataset. Results depend on the model you choose, so treat the first proposal as a draft: send a clearer request, choose **Regenerate**, or fix the details by hand after saving.

Two things help the assistant most. Name the columns you mean, because it does not see your column names unless you share them. When it cannot tell which column you meant, it asks. And describe what to change on an existing flow, because the assistant sees the node types and connections of the canvas but not the current settings of its nodes.

## Build, review and apply

1. Open a flow and choose **Assistant** in the toolbar, or **Ask the assistant** at the bottom of the canvas. The panel docks beside the canvas, and fills the screen on a narrow window. It has a **Conversation** tab and an **Activity** tab.
2. Choose the task: **Build** to create or change nodes, **Guides** to ask about Ciaren, or **Diagnose** to look at a failed run.
3. On an empty canvas choose an **Input dataset** from the flow's project. On an existing flow the assistant uses the file inputs already on the canvas and their pinned versions.
4. Describe the result and choose **Create proposal**, or press Ctrl+Enter. A progress card shows rough stages, and **Cancel request** stops the request.
5. Review the proposal. Then choose **Apply and save**, **Regenerate**, **Edit request** or **Discard**.
6. Choose **Run** in the editor when you are ready. Applying never runs the flow.

The assistant works from the saved flow. While the canvas has unsaved edits, the toolbar **Save** button carries a small dot. If you send a request before saving, the request stays in the box, **Save** pulses briefly and **Save and send** saves the canvas and sends the request.

### What a proposal shows

A proposal opens with a one-sentence summary and up to four short notes. A map of the flow follows, then every added or updated node with its settings. Each updated node lists every setting that changes, and **All settings** lists every field of a new node. Expand **Connections** to check the ports, or **Compare all settings** to inspect an existing node. **Inspect on canvas** returns to that node, and updated nodes are highlighted on the canvas while the proposal is open. Expression nodes show the whole expression, so you can read it before saving. **Steps** lists what the assistant did, such as reading dataset columns, drafting a change and checking the flow, and a line below shows the provider calls and tokens the request used.

A proposal expires after three minutes. A draft that ran out of steps or time, or lost the provider, carries a note that it was not checked. Read such a draft with extra care, or regenerate it.

After **Apply and save**, a message offers **Undo** for about 12 seconds. Undo reverses that saved change as a new revision, the same as a reversal in Activity, and works only while the canvas still matches what was saved. Later, reverse the change from Activity.

### When it asks a question

When a request leaves a real choice open, the reply is a card with one button per option instead of a proposal. A common case is a request that describes columns the types cannot identify. The buttons show your real column names, and choosing one sends the pick back as a column reference, so the name still stays on the server. A request can carry up to three answers. If no option fits, edit the request with more detail. When the assistant cannot offer options, the reply offers **Share column names and retry**.

### While it works

A request keeps running while the panel is closed, and the **Assistant** button shows a dot when the reply is ready. **Cancel request** stops the request and closes the provider connection, and so does leaving the flow. A provider can still bill work already performed. A saved-flow revision conflict, a changed input version or an expired proposal requires a new proposal. Reload the editor after a concurrent save, preserving any local work first. A reply can end with buttons for a likely next step, such as saving, sharing column names or opening a guide.

## What the assistant can build

The assistant can use these built-in nodes:

| Area | Nodes |
| --- | --- |
| Inputs and outputs | File Input and File Output; existing format-specific inputs stay readable |
| Rows | Filter, Sort, Limit, Sample, Remove Duplicates, Drop or Fill Nulls, Remove Outliers, Explode |
| Columns | Select, Drop, Rename, Cast, Combine, Coalesce, Replace or Map Values, String Transform, Split, Round, Bin, Conditional Column, date parts, date parsing and date difference |
| Combine and reshape | Join, Concatenate, Group By, Pivot, Unpivot, Window, Rolling Aggregate, Row Difference |
| Data quality | Assert Not Null, Unique, Value Range, Row Count, Values in Set and Assert Expression |
| Charts | Bar, Line, Area, Scatter, Pie, Histogram, Box Plot and Heatmap |
| Machine learning (ML extension) | Select Features, Scale, Encode, Reduce Dimensions, Train/Test Split, classifier and regressor models, training for classification, regression, clustering and dimensionality reduction, Predict, Evaluate, Feature Importance and Cross Validate |

Filter Expression, Calculated Column and Assert Expression accept a short arithmetic or comparison expression such as `price * qty > 100`. The server allows only column references, numbers, single-quoted text, comparison and arithmetic operators and the functions `abs`, `sqrt`, `exp`, `log10`, `log1p`, `sin`, `cos`, `floor` and `ceil`. The proposal highlights these nodes so you can read the expression before saving.

On an existing flow the assistant can add nodes, change the settings of nodes of these types and rewire connections. It cannot delete a node that was already on the canvas, so remove those yourself. Nodes of any other type stay as they are, and the assistant can neither edit them nor connect to them.

The assistant never writes Python Transform nodes, database or cloud storage connectors, format-specific outputs, forecasting models or plugin nodes. It cannot change credentials or file paths. Model settings are limited to the documented hyperparameters with upper bounds, for example at most 500 trees and 20 cross-validation folds. A request that needs anything else ends with an explanation instead of a partial flow. Add those nodes in the editor.

The assistant edits canvases of up to 80 nodes and 160 connections, and reads at most 64 columns of each dataset. It can use the datasets you select in the panel and those already on the canvas.

### How the assistant checks its work

The checks run on placeholder rows: each input keeps its column names, types, row count (up to 200 rows), distinct-value counts and whether a column has nulls, but every value is generated. Types and wiring are checked before you see the proposal. A value-dependent failure, such as text that does not parse as a date, appears when you run the flow, and **Diagnose** can then look at it. Data-quality nodes such as Assert Row Count pass their rows through in these checks and run when you run the flow.

Columns named after values, such as one-hot or pivot columns, have generated names in these checks, so the assistant cannot select them by name. A model node then uses every column except the target.

### Models without tool calling

The OpenCode models in the list below have no tool calling. With them, Build uses guided plans instead: up to six basic cleaning steps (limit, sort, drop nulls, remove duplicates, select or drop columns and filter), the two-input Join and the shipping regression below. A request for charts, models or other nodes is declined with a suggestion to choose a model with tool calling or to edit the canvas, or it returns no change. A model you type is assumed to support tool calling.

## Join two datasets

On an empty canvas select the left dataset, then the optional **Right input for Join**. Both must belong to the flow's project, and the right input appears only when both datasets are CSV files. With a tool-calling model, describe the join in your own words. The assistant chooses the key from the columns and builds the rest of the flow.

With a model that has no tool calling, Ciaren uses a fixed Join plan. Both CSVs need one same-named key of the same type within the first 64 columns of each input and no other overlapping column names. Open **Data shared with provider** and choose **Include column names in this request** if the question refers to specific fields. Review the two filenames, versions, key, join mode and left/right wiring before applying.

A guided Join can keep matching rows (`inner`) or retain all left rows (`left`), add one boolean equality flag on a text column, sort ascending by one input column and write a CSV. For the repository's `examples/orders-audit`, choose orders on the left and catalog on the right. Ask to keep all orders by SKU, mark `ready_to_fulfill` when `catalog_status` equals `active`, and sort by `order_id`. The flag uses Ciaren's built-in Conditional Column.

Duplicate keys can multiply rows. With null keys on both sides, pandas can match the nulls while Polars leaves them unmatched.

## Walkthrough: recover a missing order

![The flow assistant highlights a Join and previews its repair, then shows the saved change and its reversal in Activity](/screenshots/flow-assistant-join.gif)

1. Order 104 has no matching SKU in the catalog. An inner Join drops that order even though the run succeeds. In **Build**, ask to keep every order, including those without a catalog match.
2. Inspect the highlighted **Join / Merge**. The proposal changes `inner` to `left` and keeps the key and both inputs. Choose **Apply and save** when the preview matches your intent. Use **Run** separately to regenerate the CSV.
3. Open **Activity**, expand **Show details** on the saved change and select **Preview reversal**. The inverse shows `left → inner`. **Confirm reversal** adds an entry and preserves a later, unrelated sort edit. The next run uses the restored Join.

Diagnose is for runs that failed. When the latest run succeeded but rows are missing, describe the repair in Build as above. The recording uses the packaged editor, the synthetic orders audit and a simulated provider response. The canvas, validation, saves and history use the real application.

## Train a shipping cost model from three CSVs

With the ML extension enabled, Build can generate a fixed regression plan from three CSVs: two inner joins followed by a seeded train/test split, linear regression, held-out prediction, evaluation and a metrics CSV. It works with any provider, including models without tool calling. This plan starts on an empty canvas. The first CSV supplies the numeric target, and each lookup contributes one numeric predictor. Identifiers used for joining cannot be training features or targets. With a tool-calling model you can also describe a different training flow in your own words, as in the examples above.

1. Upload `orders.csv`, `customers.csv` and `catalog.csv` from the [shipping regression example](https://github.com/ciaren-labs/Ciaren/tree/main/examples/shipping-regression) into the same project. Create a blank flow there.
2. Open **Assistant → Build**. Choose orders under **Input dataset**, customers under **Right input for Join** and catalog under **Second lookup for regression**. Select **shipping_cost** as the **Regression target**.
3. Open **Data shared with provider** and allow column names for this request. Ask: **Join orders to customers and catalog. Predict shipping cost from distance and weight with linear regression. Evaluate on held-out orders.** Choose **Create proposal**.
4. Check both Join keys (`customer_id`, then `sku`), the features (`distance_km`, `weight_kg`) and the target. Check that Split's **train** port feeds the regressor while **test** and the fitted **model** feed Predict. Choose **Apply and save** after review.
5. Choose **Run**. Select **File Output → Download output**. This synthetic example keeps 80 orders, trains on 64 and evaluates 16. The reference run has mean absolute error of about 0.27 currency units and R² of 0.997.

Each lookup must have exactly one compatible key in common with the first CSV. The lookups must have distinct column names from each other. Ciaren checks the saved profile for a unique, non-null key across the whole lookup. A sampled profile cannot establish uniqueness. Both joins keep matched rows. The run needs at least 13 matching orders with usable numeric targets. The provider receives no rows or key values, so the proposal cannot establish how many orders match. Review the run counts when using your own data.

The split uses seed 42 and holds out 20% of matched rows. Only the training branch fits the model. Choose features available at prediction time. Repeated measurements or historical forecasts can need a grouped or time-based split in a manually built flow. The three selected dataset versions and the flow revision are checked again before saving.

On **Run**, the existing training node logs the fitted model and up to five rows of feature values to the installation’s configured MLflow store. That store can be remote. The LLM receives only the request and temporary join, target and predictor references by default. Opting in shares column names for that turn. When a lookup has multiple numeric candidates, Ciaren requires the opt-in to distinguish them. The model cannot choose a tracking endpoint, model URI, arbitrary hyperparameters or executable code.

## Guides, Diagnose and canvas tools

**Guides.** Ask a question about the editor, exports, parameters, scheduling or another bundled guide. The server searches the local English-language index and sends up to five matching passages to the selected model, which picks one. The answer is that passage, with a link to its exact Git revision and line. An unsupported question can return no matching passage.

**Diagnose.** Diagnose looks at this flow's most recent failed run. The server categorizes the error locally and passes the category and graph structure to the selected model. It can propose a fix in two cases: an inner Join that drops unmatched left rows, on a canvas made only of Join-related nodes, and a single-input flow of basic cleaning steps, for example when a configured column no longer exists. Any other canvas gets advice and a note that it needs a manual edit. With no failed run, Diagnose says so. For a bigger repair, describe it in Build. A proposed fix goes through the same review and save path, and an old failure may no longer match the current canvas, so check it before applying.

**Canvas tools.** **Check canvas** applies the editor's validation rules and links node-specific issues to their inspector. **Explain selected node** shows the node's summary and a tip. Both run in the browser without a provider and are on the opening screen of the Conversation tab, including when no key is set up. Only **Apply and save** commits an assistant proposal.

## Activity and reversal

Open **Assistant → Activity** to see confirmed changes for this flow, most recent first. Entries read **Proposal saved**, **Repair saved** or **Reversal**. Expand **Show details** to see node types, ports and fields, including the before and after for supported settings. Proposals, requests, provider responses, key material, rows and full graph snapshots are excluded. Activity starts with the first assistant save after upgrading. Run `ciaren db upgrade` on existing installations before starting the upgraded server. On MySQL and MariaDB the migration enables microsecond precision on flow revisions.

**Preview reversal** shows the inverse edit without changing the flow. **Confirm reversal** writes a new revision and links it to the original in the same database transaction. The original entry stays visible after reload. The editor's toolbar Undo edits the current canvas in memory, which is different. Save or discard pending canvas edits before reverting a saved revision. Viewing activity and reversing a saved change work with the provider switched off.

Reversals preserve unrelated edits when the saved inverse can be proven safe. For example, reverting a Join mode keeps a later downstream sort. Ciaren checks the project, flow revision, affected settings, dependencies and bound inputs again when you confirm. If another client saves after a preview, preserve local work, reload and preview again. A changed dependency, a removed input, or a prior private value that cannot be reconstructed requires a manual edit. Reversals are final entries in the timeline; a fresh proposal can reapply a change.

The editor sends the loaded revision on **Save** and on the save before **Run**. Run creation checks the returned revision again before taking its execution snapshot. If you edit during a Run, the editor keeps the draft open and links to the result. A conflict leaves the draft on the canvas and offers a separate tab to compare the saved version. API callers can pass `expected_revision` (the flow’s `updated_at`) on both `PUT /api/flows/{id}` and `POST /api/flows/{id}/runs`. Older clients that omit it retain unconditional save and latest-version execution; upgrade those clients to protect their writes.

Access follows the installation’s existing server authentication. The timeline records the source of a change and the user’s confirmation without attributing it to a named person. A moved flow’s prior project entries are hidden. Activity pages contain up to 20 entries. Reversal previews use up to 64 short-lived process-local references with a three-minute timeout. Use sticky routing or a single process for confirmations. Deleting the flow deletes its activity.

## What leaves the server

Every request includes the text you enter. Keep credentials and confidential row values out of that text. A column name you type in a request is matched to its column, and the model receives that name only as part of your text plus a reference for the column.

By default the model receives these facts about a Build request:

- the node catalog: node types, categories, port names and a short description;
- the canvas as node types and connections, using temporary references such as `n0` for nodes and `d0` for datasets, but not node labels or the current settings of existing nodes;
- for each dataset column it asks about, a reference and a coarse type, plus the dataset's row count and each column's null fraction, distinct count and whether the column is unique, taken from the stored profile;
- the column types and references that the placeholder-row checks report for each node, with no counts or flags such as whether a result is empty.

Other column names reach the provider only when you opt in for a single request with **Include column names in this request**. The option also sends the names of derived columns in the check results. A Join repair sends the question, a temporary Join reference, its current mode and, during diagnosis, a fixed error category. The shipping regression sends temporary join, target and predictor references. Documentation questions send up to five bundled passages without canvas context.

Files, samples, row values, filenames, dataset IDs, connection details, node labels, scripts, full configuration, raw logs and error traces stay on the server. Replies shown in the panel use the names you see in the editor, never internal references. Recommendations and citations are rendered as text. Because no check reads real values, its outcome cannot answer a guess about your data, for example whether a filter matches any row.

The assistant cannot run a pipeline. Review uses ordinary Ciaren nodes, so the existing run, export and undo controls continue to work.

## Deployment and credentials

Ciaren settings and provider credentials belong to one server instance. Anyone with access to its API can manage the assistant within the installation's token and browser-origin rules. Deploy separate instances, data directories and secret sources for separate trust boundaries. Use TLS and the Ciaren API token for a networked installation. Configure reverse proxies and monitoring to omit request bodies and authorization headers. Restrict process and diagnostic dump access at the operating-system level.

### Keys on the Connections page

Choose **Add API key** under **Connections → Assistant API keys**. Name the key, pick the provider and a model from the list, or choose **Other model…** and type the provider's exact model ID. Typed models are not tested with Ciaren. They use tool calling, so a model without it fails with a provider error. Set a reasoning effort when the provider offers one. Read the storage notice and confirm it before you save.

![Connections page with the Assistant API keys section above the data connections. One OpenAI key is in use and enabled.](/screenshots/assistant-keys.png)

Ciaren saves the key in the OS keychain of the computer that runs it: Windows Credential Manager, macOS Keychain or Secret Service. Install `ciaren[keyring]` and keep the keychain unlocked. **Add API key** stays disabled, with a note, on a computer where Ciaren finds no supported keychain, such as a headless server or container. Use the server-managed keys below there. Entries use a separate service derived from the resolved data directory. The database stores only the name, provider, model, effort and state, and Ciaren never shows a saved key again.

The assistant uses one key at a time. The first key you add becomes the one in use. To switch, select another enabled key. Clear **Enabled** to stop using a key without removing it. A disabled key cannot be selected, and disabling the key in use leaves none selected until you pick one. Use the pencil button to rename a key, change its model or effort, or replace the key. A replacement asks for the storage notice again. The provider of a saved key is fixed. **Remove** deletes the key from the keychain.

Anyone who can use this Ciaren server can run the assistant with the key in use, on your bill. Prefer a key with a spending limit.

### Server-managed keys

Without a selected key, an operator can configure the assistant in the server environment. Set `CIAREN_ASSISTANT_PROVIDER` to `openai`, `anthropic`, `deepseek`, `opencode` or `off`. Set provider-specific variables such as `CIAREN_ASSISTANT_OPENAI_MODEL` and `CIAREN_ASSISTANT_OPENAI_EFFORT`. Use the provider name in capitals. The model must be one of the listed models. Only OpenAI, Anthropic and DeepSeek expose an `_EFFORT` variable. For a direct DeepSeek API key, use `deepseek` and `deepseek-flash`. An OpenCode Go credential belongs to OpenCode. This version’s OpenCode adapter has no DeepSeek model. A key selected on the Connections page takes precedence. Set `CIAREN_ASSISTANT_ENABLED=false` and restart to turn the assistant off on the server, including saved keys.

Select the credential source per provider with `CIAREN_ASSISTANT_<PROVIDER>_KEY_SOURCE`.

| Source | Set, rotate or revoke |
| --- | --- |
| `env` (default) | Inject `CIAREN_ASSISTANT_<PROVIDER>_API_KEY` into the server process using a deployment secret. Restart after replacing or removing it. |
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

Revoke compromised keys in the provider console as well. Status checks do not contact the provider. A configured status means Ciaren found the key, not that the provider accepts it.

The server removes `CIAREN_ASSISTANT_*_API_KEY` variables from its environment at startup and from run worker processes, so flow code cannot read them from the environment. This does not protect a key from a Python Transform node. That node runs with the server's privileges and can read the key wherever it is stored: from server memory, a mounted secret file or the OS keychain. Setting `CIAREN_EXECUTION_MODE=process` keeps the keys out of the run worker's environment and settings, but it does not stop code from reading the keychain or a mounted file. On a shared installation allow only trusted users to edit flows, and use a provider key with a spending limit. See [Advanced setup](advanced-setup.md).

## Provider contracts

| Provider | Listed models | Effort in Ciaren | API family | Build mode |
| --- | --- | --- | --- | --- |
| OpenAI | `gpt-5-mini`, `gpt-5` | default, low, medium, high | Responses with storage disabled | Tool calling |
| Anthropic | `claude-sonnet-4-6` | default, low, medium, high | Messages, adaptive thinking for explicit efforts | Tool calling |
| DeepSeek | `deepseek-flash`, `deepseek-v4-pro` | default, none, low, high, max | Chat Completions | Tool calling |
| OpenCode Console | `minimax-m2.7`, `kimi-k2.6` | provider default | Paid OpenAI-compatible Chat Completions | Guided plans only |

Default omits the effort field. A typed model can be any provider model ID; it never changes the destination. Each provider has its own fixed HTTPS destination, model and credential. OpenCode's Console API routes vary by family and its free-tier chat models are restricted to OpenCode clients. Use an OpenCode Console API key for this adapter. Model availability, provider retention and charges depend on the selected provider and account. See [OpenAI reasoning](https://developers.openai.com/api/docs/guides/reasoning), [Anthropic thinking](https://platform.claude.com/docs/en/build-with-claude/extended-thinking), [DeepSeek thinking](https://api-docs.deepseek.com/guides/thinking_mode/) and [OpenCode Console inference](https://opencode.ai/docs/console/api/inference).

## Bounds and implementation

Input is limited to 1,500 request characters, 80 canvas nodes, 160 edges and 64 columns per source. One Build turn makes at most 14 provider calls and 40 tool calls within 120 seconds. Each provider call has a 35-second timeout, 4,096 output tokens and a 48 KB request limit, and each tool call 15 seconds. The opening request is at most 12 KB, and older tool results are compacted to keep each call within its limit. One edit applies up to 24 operations. Each check previews at most 50,000 rows and 2 million cells per node within 15 seconds; a single slow node step can overrun that deadline. Up to eight turns may be active per process. Up to 64 proposals live in memory for three minutes. Use a single process or sticky routing for proposal confirmation.

Each application process allows 60 provider calls per rolling hour by default (`CIAREN_ASSISTANT_TURNS_PER_HOUR`). The limit counts calls, not turns: a turn reserves its calls when it starts and returns the unused ones when it ends. A complex Build can use all 14, so the default allows about four of them an hour; raise the limit if you need more. Set `CIAREN_ASSISTANT_TOKENS_PER_HOUR` to also cap tokens. Configure provider-side spend limits for a currency-denominated cap. Requests use zero automatic retries. If a turn reaches its call limit, the assistant validates the latest draft and returns it when it passes, or returns it flagged as unchecked. The UI renders a change only after the server has validated its operations; review an unchecked draft before applying it. Cancelling a turn does not return its reserved calls.

The tools run inside the Ciaren server against the installed node registry and the same validation as the editor. The model receives turn-local references (`d0` for datasets, `n0` for nodes, `c0` for columns), never dataset IDs, file paths or rows. Every edit passes an allowlist of node types and settings before anything runs, and nothing is saved until you choose **Apply and save**. In Build, nodes of types outside the allowlist, such as plugin, code and connector nodes, stay locked. In Diagnose, flows that contain them receive read-only recommendations based on node types, wiring and the failure category. Edit those nodes in the regular editor.

The assistant has no shell, generic network or file tools, direct repository access or arbitrary code generation, and Ciaren runs no MCP listener for it. The tools already run in-process with the editor's session and checks; an MCP transport would add a second credential and authorization boundary without giving the assistant new abilities. To drive Ciaren from your own agent, see [Connect your own agent](external-agent.md). The two local canvas tools reuse existing documentation and validation. The activity endpoint handles confirmed edits separately from model tools and never provides history to the model.
