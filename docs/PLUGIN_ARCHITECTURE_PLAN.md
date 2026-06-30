# FlowFrame Plugin Marketplace & Open-Core Architecture Plan

> **Purpose:** This document is a practical implementation guide to refactor FlowFrame toward a local-first, open-source core with a future premium plugin marketplace.
>
> The goal is to make FlowFrame extensible, monetizable, and secure without requiring FlowFrame to host customer datasets, execute heavy jobs, run clusters, or manage large customer databases.

---

## Implementation Progress Tracker

> Living checklist kept in sync as the branch `feature/plugins` advances. The
> "Definition of Done" (section 24) was already met at Phase 2; the work below
> drives the remaining marketplace/security phases to a fully end-to-end system.

**Legend:** ✅ done · 🟡 partial · ⬜ not started

| Phase | Status | Notes |
|-------|--------|-------|
| 0 — Inventory | ✅ | `docs/architecture/current-architecture-map.md` |
| 1 — `.flow` schema & contracts | ✅ | `app/flow_schema/` (document/validate/migrations) + CLI `flow validate/migrate` |
| 2 — Plugin API foundation | ✅ | `app/plugin_api/` (specs, providers, registry, manifest, node_runtime) |
| 3 — Plugin loader | ✅ | `app/plugins/loader.py` (entry points + local dirs), error isolation, `/api/plugins[/diagnostics]` |
| 3.5 — Plugin state (enable/disable/permission grant) | ✅ | `app/plugins/state.py`; loader gates disabled + ungranted-permission plugins (code not imported until approved); `/api/plugins/{id}/enable\|disable\|grant\|revoke`, live registry rebuild |
| 4 — Dynamic catalog | ✅ | `/api/catalog/nodes\|connectors\|exporters\|categories`; palette renders from the catalog. (Full schema-driven config *forms* deferred — node `config_schema` isn't modeled yet; would rewrite 46 Zod forms for no functional gain today.) |
| 5 — Features as providers | ✅ | built-ins as providers; ML split into `MlNodeProvider`, registered only when `[ml]` is importable — the ETL core no longer contributes ML nodes. Engine ML imports already isolated. |
| 6 — Marketplace readiness | ✅ | `.ffplugin` zip format + deterministic digest; Ed25519 detached signatures (`app/plugin_api/signing.py`, optional `[signing]` extra); trusted-key verification; `flowframe plugin list/install/uninstall/verify/enable/disable/keygen/pack/sign/search`; license tokens + offline grace + cache + `TokenLicenseProvider`; marketplace index format. (Premium *plugins* themselves are out of scope.) |
| 7 — Security hardening | ✅ | Permission gating (code not imported until approved) + signature verification; joblib/pickle refusal & env-only DB secrets enforced; dependency-license scan (`flowframe plugin licenses`); security docs (`docs/security/`); **permission approval UI** on the frontend Plugins page (approve/enable/disable, per-permission consent). |
| 8 — Premium pilot | ⬜ | Intentionally out of scope (no premium code in the OSS core); architecture proven via signed example plugin |
| §17 — Hooks & events | ✅ | `app/plugin_api/events.py` EventBus on the registry. **Emitted:** plugin enable/disable, before/after graph execute, before/after node execute (node hooks in `thread` mode only), export requested. **Reserved (defined, not emitted yet):** `plugin_installed`, `project_*`, `graph_loaded`, `graph_validated`. |

**Out of scope (by constraint):** premium billing, cloud sync, enterprise auth,
hosted compute, and any actual premium connector implementations. The core must
remain installable and useful without any of these; premium plugins must be
installable externally without editing the core.

---

## 1. Strategic Direction

FlowFrame should evolve into a **local-first visual development environment for ETL and Machine Learning workflows**.

The business model should avoid selling hosted compute as the primary product. Instead, FlowFrame should monetize productivity, collaboration, premium connectors, advanced AI features, marketplace plugins, templates, governance, and enterprise capabilities.

### Core principle

> The user owns the data and execution environment. FlowFrame provides the visual interface, project format, plugin system, validation, code generation, and optional productivity services.

### What FlowFrame should not operate initially

Avoid offering these until there is enough scale, team capacity, and security maturity:

- Hosted Spark clusters
- Hosted notebooks
- Hosted model training
- GPU jobs
- Customer data warehouses
- Managed feature stores
- Managed MLflow servers
- Long-running customer job infrastructure
- Large customer dataset storage

### What FlowFrame marketplace can include safely

These services provide value without heavy infrastructure:

- Premium connectors
- Plugin marketplace
- AI pipeline generation
- AI debugging
- Pipeline optimization
- Advanced validation
- Advanced lineage
- Enterprise exporters
- Local license validation
- Cloud sync for metadata/project files only
- Template marketplace
- Private workspaces
- Team collaboration
- Audit logs
- RBAC
- Enterprise authentication

---

## 2. Current Architecture Assessment

Based on the architecture review, FlowFrame is **partially ready** for an open-core/plugin marketplace model.

### Strengths

- Local-first design is already strong.
- Local SQLite is used by default.
- Local execution is supported.
- Python export is aligned with reproducibility.
- The backend engine already has useful abstractions.
- Pandas/Polars separation is promising.
- The app does not currently require hosted FlowFrame infrastructure.

### Main gaps

The main problem is not the product direction. The main problem is that extensibility is not yet formalized.

Current risks:

- Node registration is static.
- Connector/provider registration is static.
- Frontend node metadata is hard-coded.
- ML is optional by dependency, not by package boundary.
- Premium features would currently require changes to the open-source core.
- There is no plugin loader.
- There is no plugin manifest.
- There is no signature verification.
- There is no plugin permission model.
- There is no local license manager.
- There is no backend-fed dynamic node catalog.

The next architectural goal is to make FlowFrame work through **stable contracts**, not static imports.

---

## 3. Target Product Boundary

FlowFrame should be designed around three layers:

```text
FlowFrame Community
  Open-source, local-first, useful by itself

FlowFrame Marketplace
  Optional plugins, some free and some premium

FlowFrame Enterprise / Cloud Services
  Optional lightweight services for licensing, sync, collaboration, governance, and AI
```

---

## 4. Open-Source vs Premium Boundary

### 4.1 Keep in open-source core

These features should remain open source because they drive adoption:

- Visual workflow editor
- DAG model
- `.flow` project format
- Local execution
- Local project storage
- Basic node system
- Basic validation
- Python export (pandas / polars / polars-lazy variants today)
- Notebook export *(not implemented yet — planned)*
- CLI
- CSV / Excel / Parquet / JSON / text support
- Basic pandas nodes
- Basic Polars nodes
- Basic SQL connector (DuckDB ships today as a SQL connector provider, not a dataframe engine)
- Basic storage connectors
- Basic scikit-learn nodes
- Documentation
- Examples
- Community templates

### 4.2 Keep open source but isolate as optional plugins

These can remain free but should be separated from the core:

- ML nodes
- Quality assertion nodes
- MLflow integration
- Cloud storage connectors
- Basic visualization nodes
- Basic exporters
- Example plugin implementations

This improves modularity without weakening the community product.

### 4.3 Premium candidates

These have clear commercial value:

- Databricks connector
- Snowflake connector
- BigQuery connector
- Microsoft Fabric connector
- SAP connector
- Salesforce connector
- ServiceNow connector
- SAP HANA connector
- Teradata connector
- Advanced AI pipeline builder
- AI debugger
- Pipeline optimizer
- Advanced lineage
- Impact analysis
- Enterprise exporters
- Cloud sync
- Private workspaces
- Marketplace license manager
- Signed private plugins
- Team collaboration
- RBAC
- Audit logs
- Enterprise authentication

### 4.4 Recommendation on ML

Do **not** remove all ML from the open-source product too early.

FlowFrame's differentiation is ETL + ML. If ML is removed from the community version, FlowFrame risks becoming just another visual ETL or automation tool.

Recommended split:

#### Community ML

- scikit-learn
- train/test split
- preprocessing
- metrics
- baseline models
- XGBoost / LightGBM / CatBoost if dependency handling is clean
- basic model evaluation
- basic model export

#### Premium ML / AI

- AutoML
- AI pipeline generation
- AI debugger
- feature leakage detection
- optimization recommendations
- RAG pipeline generation
- LLM workflow nodes
- advanced explainability
- experiment comparison UI
- production deployment exporters

---

## 5. Recommended Target Repository Structure

A future-proof structure could look like this:

```text
flowframe/
  apps/
    web/
    desktop/
    api/

  packages/
    flowframe-schema/
    flowframe-core/
    flowframe-engine/
    flowframe-plugin-api/
    flowframe-plugin-loader/
    flowframe-ui-shell/
    flowframe-connectors-basic/
    flowframe-nodes-basic/
    flowframe-validators-basic/
    flowframe-exporters-basic/
    flowframe-cli/

  plugins/
    community/
      flowframe-plugin-ml-basic/
      flowframe-plugin-quality/
      flowframe-plugin-mlflow/
      flowframe-plugin-storage-cloud-basic/

  enterprise/
    flowframe-license-client/
    flowframe-cloud-sync-client/
    flowframe-auth-providers/
    flowframe-audit/
    flowframe-rbac/

  marketplace/
    plugin-manifest-schema/
    signing-tools/
    local-license-tools/

  docs/
  examples/
```

### Independently publishable packages

These should eventually be publishable independently:

- `flowframe-schema`
- `flowframe-core`
- `flowframe-engine`
- `flowframe-plugin-api`
- `flowframe-plugin-loader`
- `flowframe-connectors-basic`
- `flowframe-nodes-basic`
- `flowframe-validators-basic`
- `flowframe-exporters-basic`
- `flowframe-cli`

Premium plugins can later be published privately as wheels, signed packages, compiled artifacts, or marketplace downloads.

---

## 6. The `.flow` Format

The `.flow` format should become a public, stable, versioned specification.

This is one of the most important architectural decisions.

Do not treat `.flow` as an internal JSON blob. Treat it as a product-level contract.

> **Current state:** there is no `.flow` *file* yet. A flow persists in the
> database as React Flow-compatible `graph_json` (`nodes`/`edges`, plus
> `graph_json.parameters` and `graph_json.engine`). A portable "flow document"
> already exists via `POST /api/flows/import` and the `flow_document` returned by
> `POST /api/flows/{id}/export/python` — but it is unversioned and strips
> environment-specific bindings (dataset / connection ids) on import. The work
> below is to **formalize and version that existing document**, not to invent a
> new one from scratch.

### Why this matters

A stable `.flow` spec enables:

- long-term backward compatibility
- plugin interoperability
- LLM-generated pipelines
- external tools that generate FlowFrame projects
- marketplace templates
- project validation without the full app
- reliable import/export
- easier testing
- easier migration between versions

### Recommended package

Create:

```text
packages/flowframe-schema/
  flowframe_schema/
    graph.schema.json
    node.schema.json
    edge.schema.json
    port.schema.json
    metadata.schema.json
    execution.schema.json
    plugin.schema.json
    migrations/
```

### Minimum fields

A `.flow` file should include:

```json
{
  "schemaVersion": "1.0.0",
  "flowframeVersion": "0.1.0",
  "project": {
    "id": "...",
    "name": "...",
    "description": "..."
  },
  "graph": {
    "nodes": [],
    "edges": []
  },
  "metadata": {},
  "requirements": {
    "plugins": [],
    "capabilities": []
  }
}
```

### Required capabilities

Each flow should be able to declare required capabilities:

```json
{
  "requirements": {
    "plugins": [
      {
        "id": "flowframe.databricks",
        "version": ">=1.0,<2.0",
        "required": true
      }
    ],
    "capabilities": [
      "connector.sql",
      "engine.polars",
      "exporter.python"
    ]
  }
}
```

### Migration policy

Implement schema migrations from day one:

```text
1.0.0 -> 1.1.0
1.1.0 -> 1.2.0
```

Rules:

- Never silently mutate a user project without a backup.
- Always keep migration tests.
- Keep old schemas available for validation.
- Include a CLI migration command.

Example:

```bash
flowframe migrate project.flow --to 1.2.0
```

---

## 7. Plugin API

Create a stable `flowframe-plugin-api` package.

This package should contain interfaces only. It should not depend on the full backend or frontend app.

### Required interfaces

Recommended interfaces:

```python
class Plugin:
    def metadata(self) -> PluginMetadata: ...
    def register(self, registry: PluginRegistry) -> None: ...
```

```python
class NodeProvider:
    def nodes(self) -> list[NodeSpec]: ...
```

```python
class ConnectorProvider:
    def connectors(self) -> list[ConnectorSpec]: ...
```

```python
class StorageProvider:
    def storage_backends(self) -> list[StorageSpec]: ...
```

```python
class ExecutionProvider:
    def execution_backends(self) -> list[ExecutionSpec]: ...
```

```python
class ExporterProvider:
    def exporters(self) -> list[ExporterSpec]: ...
```

```python
class ValidatorProvider:
    def validators(self) -> list[ValidatorSpec]: ...
```

```python
class AIProvider:
    def ai_capabilities(self) -> list[AICapabilitySpec]: ...
```

```python
class AuthProvider:
    def auth_methods(self) -> list[AuthMethodSpec]: ...
```

```python
class LicenseProvider:
    def validate_license(self, plugin_id: str) -> LicenseStatus: ...
```

### Core rule

No premium or optional plugin should need to import private internals from the main app.

Plugins should depend on:

```text
flowframe-plugin-api
flowframe-schema
```

They should not depend on unstable internals.

---

## 8. Plugin Manifest

Every plugin should include a manifest.

Example:

```yaml
id: flowframe.databricks
name: Databricks Connector
version: 1.0.0
publisher: flowframe
license: commercial
flowframe: ">=1.0,<2.0"
entrypoint: flowframe_databricks.plugin:DatabricksPlugin
permissions:
  - network
  - credentials
  - filesystem_read
capabilities:
  - connector.databricks
  - exporter.databricks_job
ui:
  nodes:
    - databricks.read_table
    - databricks.write_table
billing:
  type: paid
  licenseRequired: true
```

### Manifest requirements

The manifest must declare:

- plugin id
- name
- version
- publisher
- license type
- FlowFrame compatibility
- backend entry point
- permissions
- capabilities
- UI contributions
- dependencies
- whether a license is required
- whether the plugin is trusted, verified, or community-submitted

---

## 9. Plugin Loader

Create `flowframe-plugin-loader`.

The loader should be responsible for:

1. Discovering installed plugins.
2. Reading manifests.
3. Validating compatibility.
4. Validating signatures.
5. Checking licenses.
6. Checking permissions.
7. Loading entry points.
8. Registering providers.
9. Reporting plugin errors without crashing the app.

### Discovery mechanisms

Support at least:

- Python entry points
- local plugin directory
- development plugin path

Example locations:

```text
~/.flowframe/plugins/
./plugins/
```

### Python entry point example

```toml
[project.entry-points."flowframe.plugins"]
databricks = "flowframe_databricks.plugin:DatabricksPlugin"
```

### Loader behavior

The loader should never blindly import everything.

Recommended order:

1. Find candidate package.
2. Read manifest.
3. Validate manifest schema.
4. Validate version compatibility.
5. Validate signature if required.
6. Check license if required.
7. Ask for permissions if needed.
8. Import plugin entry point.
9. Register capabilities.

---

## 10. Dynamic Node Catalog

The frontend must not hard-code all node metadata.

Instead, the backend should expose the catalog generated from core and installed plugins.

### Proposed endpoint

```http
GET /api/catalog/nodes
```

Response:

```json
[
  {
    "id": "filterRows",
    "label": "Filter Rows",
    "category": "Cleaning",
    "description": "Filter rows using an expression.",
    "provider": "flowframe.nodes.basic",
    "version": "1.0.0",
    "inputs": [
      {"id": "in", "type": "dataframe"}
    ],
    "outputs": [
      {"id": "out", "type": "dataframe"}
    ],
    "configSchema": {},
    "uiSchema": {},
    "permissions": [],
    "capabilities": []
  }
]
```

> **Note:** node ids match the registry today (`app/engine/registry.py`):
> engine-agnostic camelCase types such as `filterRows`, `dropColumns`,
> `groupByAggregate`. A single transformation runs on either engine, so nodes do
> **not** carry an `engine.*` capability — the engine is selected per run
> (`settings.DEFAULT_ENGINE`, overridable per request). Handle ids follow the
> existing `in`/`out` convention.

### Frontend responsibility

React should render the catalog. It should not own business knowledge about nodes.

The frontend can still define:

- generic node renderer
- icon mapping
- layout logic
- schema-driven forms
- validation display
- documentation display

But it should not require recompilation when a plugin adds a new node.

---

## 11. Capability Registry

Plugins should register capabilities, not just classes.

Example capabilities:

```text
connector.sql
connector.snowflake
connector.databricks
storage.s3
storage.azure_blob
engine.pandas
engine.polars
validator.quality
exporter.python
exporter.notebook
exporter.airflow
exporter.databricks
ai.pipeline_builder
ai.debugger
ai.optimizer
```

> **Implemented today:** `engine.pandas`, `engine.polars`, `connector.sql`
> (incl. DuckDB), `connector.mongo`, `storage.s3`/`storage.azure_blob`/`storage.gcs`,
> `validator.quality`, and `exporter.python`. The rest are aspirational targets
> for the marketplace, not current capabilities.

### Why capabilities matter

Capabilities allow:

- plugin compatibility checks
- project requirements validation
- graceful missing-plugin messages
- marketplace recommendations
- premium feature gating
- export-time validation

Example user message:

```text
This project requires connector.databricks.
Install the Databricks Connector plugin to continue.
```

---

## 12. Permission Model

Plugins should declare permissions.

Recommended initial permission types:

```text
filesystem_read
filesystem_write
network
credentials
subprocess
shell
docker
local_model_load
joblib_load
database_access
cloud_access
llm_access
telemetry
```

### Permission rules

- The manifest must declare requested permissions.
- The UI should show permissions before enabling a plugin.
- Dangerous permissions should require explicit confirmation.
- Permissions should be stored locally.
- The user should be able to revoke permissions.
- Enterprise mode should allow admins to restrict permissions.

### Important note

Python plugins are not fully sandboxed by default. The permission model is initially a trust and UX boundary, not a hard security sandbox.

Document this clearly.

---

## 13. Signature Verification

Premium and verified marketplace plugins should be signed.

### Recommended flow

1. Build plugin artifact.
2. Generate hash.
3. Sign hash with marketplace private key.
4. Publish artifact and signature.
5. Local app verifies signature using FlowFrame public key.
6. Refuse installation if signature does not match.

### What signatures protect against

- tampered packages
- compromised download URLs
- accidental corruption
- unofficial modified premium packages being presented as official

### What signatures do not fully protect against

- users copying already-installed files
- reverse engineering Python code
- malicious behavior in a signed but poorly reviewed plugin

---

## 14. Local License Validation

Premium plugins should run locally, but license checks can use a lightweight cloud service.

### Recommended license behavior

- User buys plugin in marketplace.
- User signs into FlowFrame locally.
- App downloads license token.
- License token is cached locally.
- Plugin can run offline for a grace period.
- License periodically refreshes.

### License token should include

```json
{
  "userId": "...",
  "pluginId": "flowframe.databricks",
  "licenseType": "pro",
  "expiresAt": "2027-01-01T00:00:00Z",
  "offlineGraceUntil": "2027-01-15T00:00:00Z",
  "signature": "..."
}
```

### Important tradeoff

Local licensing can be bypassed by determined attackers. The goal is to prevent casual unauthorized use, not to create impossible DRM.

Do not over-engineer DRM early.

---

## 15. Premium Plugin Distribution

Premium plugins can be distributed as:

- private Python wheels
- signed `.ffplugin` zip packages
- compiled Python extensions
- Rust/Cython binaries for sensitive logic
- hybrid local package + remote API for AI features

### Recommended first approach

Start with signed Python wheels or signed `.ffplugin` packages.

This is simpler and good enough for early paid users.

### For sensitive IP

For AI optimizers or proprietary algorithms:

- keep the model/prompt/orchestration remote, or
- compile critical parts, or
- expose only a local interface that calls a service

Do not assume Python source can be fully hidden.

---

## 16. Service Registry

Avoid global registries and scattered imports.

Introduce a `ServiceRegistry` or `CapabilityRegistry`.

Example responsibilities:

```text
register_node_provider()
register_connector_provider()
register_storage_provider()
register_exporter_provider()
register_validator_provider()
register_ai_provider()
get_capability()
list_capabilities()
resolve_provider()
```

### Rule

Core should not know about Snowflake, Databricks, or other premium implementations.

Core should know only about interfaces and capabilities.

---

## 17. Hooks and Events

Add an event system so plugins can extend behavior without modifying core.

Recommended hooks:

```text
on_project_created
on_project_opened
on_project_saved
on_graph_loaded
on_graph_validated
before_node_execute
after_node_execute
before_graph_execute
after_graph_execute
on_export_requested
on_plugin_installed
on_plugin_enabled
on_plugin_disabled
```

### Use cases

- audit plugin logs executions
- AI plugin suggests improvements after validation
- documentation plugin updates docs on save
- lineage plugin captures graph changes
- exporter plugin adds deployment options

---

## 18. Security Considerations

### Current local-first trust model

For the MVP, FlowFrame can assume a trusted local user.

However, before adding marketplace, teams, or enterprise mode, the app needs clearer boundaries.

### Required security improvements

- Do not store raw secrets in `.flow` files.
- Store references to environment variables or local secret stores.
- Add plugin signature verification.
- Add permission declarations.
- Add plugin compatibility checks.
- Add license token signature verification.
- Add dependency license scanning.
- Add safe loading warnings for `.joblib` and pickle-like formats.
- Add read-only connection modes for SQL connectors.
- Add SQL execution warnings and permission gates.
- Avoid arbitrary dynamic imports without manifest validation.

### Special risks

#### Custom SQL

Custom SQL is powerful but dangerous in shared environments.

For local MVP, it is acceptable.

For enterprise mode, add:

- read-only connection support
- query allow/block lists
- query previews
- execution permissions
- audit logs

#### joblib / pickle

`joblib.load` can execute arbitrary code.

Add warnings and permission gates:

```text
This model file may execute code when loaded. Only load files you trust.
```

---

## 19. Licensing Considerations

Apache-2.0 is compatible with premium extensions.

Recommended approach:

- Keep core Apache-2.0.
- Keep plugin API Apache-2.0.
- Keep basic community plugins Apache-2.0.
- Make premium plugins commercial/private.
- Protect the FlowFrame brand with trademark rules.
- Add a dependency license scan before releases.

### Important

The license protects the code. It does not protect the brand strategy.

Create:

```text
TRADEMARKS.md
BRAND_GUIDELINES.md
```

This helps prevent others from offering a confusingly similar “FlowFrame Cloud” using your name.

---

## 20. Recommended Implementation Phases

## Phase 0: Architecture Freeze and Inventory

Goal: understand current boundaries before refactoring.

Tasks:

1. Map current backend modules.
2. Map current frontend node catalog.
3. Identify all static registries.
4. Identify all connectors and provider maps.
5. Identify ML-related imports.
6. Identify storage/secrets logic.
7. Identify export logic.
8. Identify all places where frontend duplicates backend knowledge.

Deliverable:

```text
docs/architecture/current-architecture-map.md
```

---

## Phase 1: Stable Schema and Contracts

Goal: create stable contracts before building plugins.

Tasks:

1. Create `flowframe-schema`.
2. Define `.flow` schema.
3. Define node schema.
4. Define edge schema.
5. Define port schema.
6. Define metadata schema.
7. Define plugin manifest schema.
8. Add schema validation.
9. Add schema migration framework.
10. Add CLI command for schema validation.

Deliverables:

```text
packages/flowframe-schema/
docs/specs/flow-format.md
docs/specs/plugin-manifest.md
```

---

## Phase 2: Plugin API Foundation

Goal: define the public extension contracts.

Tasks:

1. Create `flowframe-plugin-api`.
2. Define `Plugin` interface.
3. Define `NodeProvider`.
4. Define `ConnectorProvider`.
5. Define `StorageProvider`.
6. Define `ExecutionProvider`.
7. Define `ExporterProvider`.
8. Define `ValidatorProvider`.
9. Define `AIProvider`.
10. Define `AuthProvider`.
11. Define `LicenseProvider`.
12. Define shared data classes/specs.
13. Add documentation and examples.

Deliverables:

```text
packages/flowframe-plugin-api/
docs/plugins/writing-a-plugin.md
examples/plugins/basic-node-plugin/
```

---

## Phase 3: Plugin Loader

Goal: support installable plugins.

Tasks:

1. Create `flowframe-plugin-loader`.
2. Add plugin discovery.
3. Add manifest validation.
4. Add Python entry point support.
5. Add local plugin directory support.
6. Add development plugin path support.
7. Add compatibility checks.
8. Add error isolation.
9. Add plugin enable/disable state.
10. Add plugin diagnostics endpoint.

Deliverables:

```text
packages/flowframe-plugin-loader/
GET /api/plugins
GET /api/plugins/diagnostics
```

---

## Phase 4: Dynamic Catalog

Goal: remove frontend hard-coded node catalog dependency.

Tasks:

1. Backend aggregates node specs from core and plugins.
2. Add `GET /api/catalog/nodes`.
3. Add `GET /api/catalog/connectors`.
4. Add `GET /api/catalog/exporters`.
5. Update frontend to render schema-driven nodes.
6. Update frontend to render schema-driven config forms.
7. Remove duplication from `frontend/src/lib/nodeCatalog.ts` where possible.

Deliverables:

```text
backend catalog endpoints
frontend dynamic node catalog renderer
```

---

## Phase 5: Convert Existing Features into Providers

Goal: replace static registries with provider registration.

Tasks:

1. Convert built-in nodes into `NodeProvider`.
2. Convert connectors into `ConnectorProvider`.
3. Convert storage backends into `StorageProvider`.
4. Convert exporters into `ExporterProvider`.
5. Convert validators into `ValidatorProvider`.
6. Convert ML nodes into an optional provider.
7. Remove direct imports of optional feature modules from the core registry.
8. Add tests ensuring providers can be loaded/unloaded independently.

Deliverables:

```text
flowframe-nodes-basic
flowframe-connectors-basic
flowframe-validators-basic
flowframe-exporters-basic
flowframe-plugin-ml-basic
```

---

## Phase 6: Marketplace Readiness

Goal: prepare the local app for future premium plugin installation.

Tasks:

1. Define `.ffplugin` package format or signed wheel policy.
2. Add signature verification.
3. Add trusted publisher metadata.
4. Add local plugin installation command.
5. Add local plugin uninstall command.
6. Add marketplace index format.
7. Add plugin search/list metadata structure.
8. Add license token model.
9. Add offline grace period.
10. Add local license cache.

Deliverables:

```text
flowframe plugin install <plugin>
flowframe plugin uninstall <plugin>
flowframe plugin list
flowframe plugin verify <plugin>
```

---

## Phase 7: Security Hardening

Goal: make the plugin system safe enough for early marketplace use.

Tasks:

1. Add plugin permission declarations.
2. Add permission approval UI.
3. Add permission storage.
4. Add permission revocation.
5. Add warnings for dangerous capabilities.
6. Add SQL execution safety options.
7. Add joblib/pickle warnings.
8. Add dependency license scanning.
9. Add plugin diagnostics logs.
10. Add trust model documentation.

Deliverables:

```text
docs/security/plugin-security.md
docs/security/local-first-trust-model.md
```

---

## Phase 8: Premium Plugin Pilot

Goal: test premium architecture with one real plugin.

Recommended first premium plugin candidates:

1. Databricks connector/exporter
2. Snowflake connector
3. AI Pipeline Builder
4. Pipeline Optimizer

Recommended first choice:

```text
Databricks connector/exporter
```

Why:

- clear enterprise value
- does not require hosting compute
- users already have Databricks infrastructure
- FlowFrame only generates/exports/integrates
- easy to justify as premium

Deliverables:

```text
private plugin repository
signed plugin artifact
local install flow
license check
```

---

## 21. Suggested Premium Roadmap

### First paid product

A premium connector/exporter is the simplest first paid product.

Recommended:

- Databricks Connector + Databricks Job Exporter

Features:

- connect to Databricks SQL Warehouse
- browse catalogs/schemas/tables
- read Delta tables
- write Delta tables
- export FlowFrame pipeline as Databricks job
- generate deployment bundle
- validate cluster/job configuration

### Second paid product

AI Pipeline Builder.

Features:

- natural language to flow
- generate ETL pipeline
- generate ML pipeline
- explain generated nodes
- recommend missing validation steps

### Third paid product

Pipeline Optimizer.

Features:

- detect expensive joins
- recommend Polars lazy mode (note: Python export already emits a polars-lazy
  variant today — the premium value is *analysis/recommendation*, not codegen)
- detect unused columns
- detect unnecessary materialization
- estimate memory risk
- suggest pushdown filters

---

## 22. Questions for Product Owner

Before implementation, answer these questions:

1. Should FlowFrame be a desktop app, local web app, or both?
2. Should ML basic remain in the community version?
3. Which cloud storage connectors should remain free?
4. What is the first premium plugin?
5. Should plugins be allowed to execute arbitrary Python?
6. How much plugin sandboxing is required for MVP?
7. Should the marketplace support third-party developers from the start?
8. Should licenses be per-user, per-machine, per-team, or per-plugin?
9. Should enterprise plugins live in the monorepo initially or separate private repositories?
10. Should `.flow` be positioned as an open specification?

Recommended answers for now:

1. Start with local web app + CLI; desktop can come later.
2. Keep basic ML in community.
3. Keep S3/Azure Blob/GCS free if maintenance cost is manageable.
4. Start with Databricks or Snowflake.
5. Allow arbitrary Python only for trusted plugins.
6. Start with permission prompts, not full sandboxing.
7. Not initially; support official/community plugins first.
8. Start per-user/per-plugin with offline grace period.
9. Use separate private repos for premium once plugin API stabilizes.
10. Yes, make `.flow` a public versioned spec.

---

## 23. Immediate Implementation Notes

Prepare the architecture for a future open-core plugin marketplace while keeping
the current product local-first and open source.

Do not implement premium billing or marketplace UI yet. Focus on architectural
foundations:

1. Identify all static registries for nodes, connectors, providers, validators,
   exporters, and ML features.
2. Propose a minimal `flowframe-schema` package for the `.flow` format.
3. Propose a minimal `flowframe-plugin-api` package with interfaces for Plugin,
   NodeProvider, ConnectorProvider, StorageProvider, ExecutionProvider,
   ExporterProvider, ValidatorProvider, AIProvider, AuthProvider, and
   LicenseProvider.
4. Propose a minimal `flowframe-plugin-loader` that can discover plugins via
   Python entry points and local plugin directories.
5. Propose backend catalog endpoints so the frontend can receive node metadata
   dynamically instead of hard-coding all nodes in React.
6. Keep basic ETL and basic ML community-friendly.
7. Do not move code to private packages yet; first create boundaries and
   interfaces.
8. Add tests proving that a sample plugin can register a node and that the
   frontend/backend catalog can see it.

Prioritize safe incremental refactoring over large rewrites.

---

## 24. Definition of Done

This architecture effort is successful when:

- The `.flow` schema is versioned and documented.
- The plugin API exists as a stable package.
- The plugin loader can discover at least one sample plugin.
- Nodes can be registered without editing the core registry.
- Connector providers can be registered without editing a central static provider map.
- The frontend receives node metadata from the backend.
- A sample plugin can add a node and appear in the UI.
- Plugin manifests are validated.
- Plugin compatibility is checked.
- Permissions are represented in the manifest, even if enforcement is basic.
- Premium/private plugins are architecturally possible without changing the open-source core.
- Existing community features still work.

---

## 25. Final Recommendation

Do not start monetization by hiding the whole product.

Instead:

1. Keep FlowFrame useful and open source.
2. Make the architecture plugin-first.
3. Make `.flow` a stable public format.
4. Keep execution local.
5. Monetize premium plugins and productivity features.
6. Avoid heavy hosted compute.
7. Start with one premium connector or one AI capability.
8. Add cloud services only when they support licensing, metadata sync, collaboration, or AI—not core execution.

This gives FlowFrame the best chance to grow as an open-source project while still leaving a realistic path to a sustainable business.
