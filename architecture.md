# Architecture

## Overview

This project is a lightweight visual ETL builder.

The application has:

- A React frontend for visual flow creation.
- A FastAPI backend for persistence, validation, execution, preview, and code generation.
- A pandas-based execution engine.
- SQLAlchemy as the database abstraction layer.
- Alembic for migrations.
- SQLite as the default local database.

The first version should optimize for simplicity, local development, and clarity.

## Architecture Goals

1. Make ETL flows easy to create visually.
2. Keep deployment simple.
3. Support common tabular data cleaning operations.
4. Generate readable Python/pandas code.
5. Avoid locking the app into a specific database.
6. Keep the transformation engine independent from FastAPI.
7. Allow future support for Polars, DuckDB, cloud storage, and scheduled runs.

## High-Level Diagram

```text
┌───────────────────────────┐
│        React Frontend      │
│  Vite + TypeScript         │
│  @xyflow/react             │
│  shadcn/ui                 │
└─────────────┬─────────────┘
              │ REST API
              ▼
┌───────────────────────────┐
│        FastAPI Backend     │
│  Routes + Services         │
│  Pydantic Schemas          │
└─────────────┬─────────────┘
              │
      ┌───────┴────────┐
      ▼                ▼
┌──────────────┐ ┌──────────────────┐
│ SQLAlchemy   │ │ ETL Engine        │
│ ORM + DB     │ │ pandas executor   │
│ Alembic      │ │ code generation   │
└──────────────┘ └──────────────────┘
```

## Frontend Architecture

### Stack

- React
- TypeScript
- Vite
- @xyflow/react
- TanStack Query
- Zustand
- shadcn/ui
- Tailwind CSS
- React Hook Form
- Zod

### Responsibilities

The frontend is responsible for:

- Rendering the visual DAG editor.
- Letting users create, edit, and connect nodes.
- Displaying node configuration forms.
- Uploading datasets.
- Showing schema and data previews.
- Triggering flow previews and executions.
- Showing run status and errors.
- Displaying generated Python code.

The frontend should not execute ETL logic. It only builds and submits graph definitions.

### Main Frontend Modules

```text
src/
├── components/
│   ├── ui/
│   ├── flow/
│   │   ├── FlowCanvas.tsx
│   │   ├── FlowNode.tsx
│   │   ├── NodeSidebar.tsx
│   │   └── nodeTypes.ts
│   └── layout/
├── features/
│   ├── flows/
│   ├── datasets/
│   ├── runs/
│   └── transformations/
├── lib/
│   ├── api.ts
│   ├── queryClient.ts
│   └── validators.ts
├── stores/
│   └── flowEditorStore.ts
└── main.tsx
```

### Frontend State

Use two kinds of state:

#### Server state

Use TanStack Query for:
- Flow list
- Flow details
- Dataset list
- Dataset sample
- Run status
- Generated code

#### Local editor state

Use Zustand for:
- Currently selected node
- Unsaved graph state
- Sidebar open/closed state
- Preview panel state

## Backend Architecture

### Stack

- FastAPI
- Pydantic v2
- SQLAlchemy 2.x
- Alembic
- pandas
- pytest

### Backend Layers

```text
API Routes
   ↓
Services
   ↓
Repositories
   ↓
SQLAlchemy Models
```

The ETL engine is called by services, not directly by API routes.

### Backend Modules

```text
app/
├── api/
│   ├── deps.py
│   └── routes/
├── core/
│   ├── config.py
│   ├── database.py
│   └── logging.py
├── db/
│   ├── models/
│   └── repositories/
├── schemas/
├── services/
├── engine/
└── main.py
```

## Database Architecture

The app should use SQLAlchemy as the abstraction layer.

### Default

For local development set env variables of the database, for example:

```env
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/etl_visual
DATABASE_URL=mysql+aiomysql://user:password@localhost:3306/etl_visual
```

### Alembic

Use Alembic for all schema migrations.

Rules:
- Do not manually alter database schema outside migrations.
- Each model change should have a migration.
- Migration files should be reviewed before commit.
- Keep SQLite compatibility in mind during MVP.

## Core Tables

### flows

Stores saved ETL graphs.

Columns:
- id
- name
- description
- graph_json
- created_at
- updated_at

### datasets

Stores uploaded or registered datasets.

Columns:
- id
- name
- source_type
- location
- schema_json
- sample_json
- created_at
- updated_at

### flow_runs

Stores execution metadata.

Columns:
- id
- flow_id
- input_dataset_id
- status
- output_location
- started_at
- finished_at
- error_message
- logs_json

## ETL Engine Architecture

The ETL engine is independent from FastAPI.

It should be usable from:
- API services
- CLI in the future
- tests
- generated scripts

### Engine Modules

```text
engine/
├── graph.py
├── registry.py
├── executor.py
├── codegen.py
└── transformations/
    ├── base.py
    ├── clean.py
    ├── reshape.py
    ├── join.py
    └── aggregate.py
```

### Transformation Interface

Each transformation should expose:

```python
class BaseTransformation:
    type: str

    def validate_config(self, config: dict) -> None:
        raise NotImplementedError

    def execute(self, inputs: dict, config: dict) -> dict:
        raise NotImplementedError

    def to_python_code(self, input_vars: dict, output_vars: dict, config: dict) -> str:
        raise NotImplementedError
```

Use `inputs` and `outputs` as dictionaries so the design can later support joins and multi-input nodes.

## Graph Execution

Execution steps:

1. Load flow graph.
2. Validate nodes and edges.
3. Detect cycles.
4. Topologically sort nodes.
5. Resolve input datasets.
6. Execute each node.
7. Store intermediate previews when needed.
8. Write final output.
9. Save run metadata.

## Graph Validation Rules

A valid graph must:

- Have at least one input node.
- Have at least one output node.
- Have no cycles.
- Use known node types.
- Have valid configuration for every node.
- Respect allowed input/output handle counts.
- Not contain orphan transformation nodes.

## Initial Transformations

### Input

- CSV input
- Excel input
- Parquet input

### Cleaning

- Rename columns
- Drop columns
- Select columns
- Drop nulls
- Fill nulls
- Remove duplicates
- Change types
- Filter rows
- Sort rows

### Transform

- Group by aggregate
- Join/merge
- Concatenate rows
- Create calculated column

### Output

- CSV output
- Excel output
- Parquet output

## API Architecture

Base path:

```text
/api
```

### Flows

```text
GET    /api/flows
POST   /api/flows
GET    /api/flows/{flow_id}
PUT    /api/flows/{flow_id}
DELETE /api/flows/{flow_id}
```

### Datasets

```text
POST /api/datasets/upload
GET  /api/datasets
GET  /api/datasets/{dataset_id}
GET  /api/datasets/{dataset_id}/schema
GET  /api/datasets/{dataset_id}/sample
```

### Runs

```text
POST /api/flows/{flow_id}/runs
GET  /api/runs/{run_id}
```

### Preview

```text
POST /api/flows/{flow_id}/preview
POST /api/transformations/preview
```

### Code generation

```text
POST /api/flows/{flow_id}/export/python
```

## File Storage

For MVP, store uploaded files locally.

Recommended structure:

```text
.data/
├── uploads/
├── outputs/
└── previews/
```

Make the base data directory configurable:

```env
DATA_DIR=.data
```

Future storage adapters:
- Local filesystem
- S3
- Azure Blob Storage
- Google Cloud Storage

## Configuration

Use environment variables.

Example:

```env
APP_NAME=ETL Visual
ENVIRONMENT=development
DATABASE_URL=sqlite+aiosqlite:///./etl_visual.db
DATA_DIR=.data
CORS_ORIGINS=http://localhost:5173
```

## Error Handling

Backend errors should return structured responses:

```json
{
  "error": {
    "code": "INVALID_TRANSFORMATION_CONFIG",
    "message": "Column 'email' does not exist in the input dataframe.",
    "details": {
      "node_id": "drop_nulls_1",
      "column": "email"
    }
  }
}
```

## Security Considerations

For MVP:

- Validate uploaded file type.
- Limit uploaded file size.
- Do not execute arbitrary user Python.
- Restrict calculated columns to a safe expression system.
- Sanitize file paths.
- Avoid exposing local filesystem paths in API responses.

Important: never implement arbitrary Python execution from the UI in MVP.

## Code Generation

The code generation service should produce readable Python.

Example:

```python
import pandas as pd

df_1 = pd.read_csv("input.csv")
df_2 = df_1.dropna(subset=["email"])
df_3 = df_2.rename(columns={"old_name": "new_name"})
df_3.to_csv("output.csv", index=False)
```

Generated code should:
- Be deterministic.
- Include imports.
- Use clear variable names.
- Prefer pandas operations that are easy to understand.
- Avoid clever chained expressions in MVP.

## Deployment Architecture

MVP local deployment:

```text
frontend: Vite dev server
backend: Uvicorn/FastAPI
database: SQLite
storage: local filesystem
```

Simple Docker deployment:

```text
docker-compose
├── backend
├── frontend
└── optional database
```

Do not require Docker for local development.

## Future Architecture Extensions

Possible future additions:

- CLI runner
- Scheduled runs
- Cloud storage adapters
- Database connectors
- Polars execution engine
- DuckDB SQL nodes
- User authentication
- Workspace support
- Template gallery
- Plugin system for custom transformations
- Python package export
- Hosted SaaS version

## MVP Boundary

The MVP should be considered successful when it supports:

1. Local installation.
2. CSV upload.
3. Visual flow creation.
4. At least five working transformations.
5. Data preview.
6. Full flow execution.
7. Output export.
8. Python code generation.
