# CLAUDE.md

## Project Summary

This project is an open-source visual ETL builder focused on simple, local-first, pandas-based data transformations.

The goal is not to compete with Airflow, dbt, Spark, or enterprise orchestration platforms. The goal is to provide a lightweight tool where users can visually build common ETL flows through a React interface, execute them through a Python/FastAPI backend, and optionally export the generated Python code.

## Product Vision

Create the simplest possible visual ETL tool for small and medium datasets.

Primary user:
- Analysts
- Data-curious business users
- Python beginners
- Developers who want quick repeatable pandas pipelines
- Educators teaching pandas/data cleaning

Core promise:
> Upload or connect data, build a visual cleaning pipeline, preview results, run it, and export readable Python code.

## Non-Goals for MVP

Do not build these in the first version:
- Airflow replacement
- Distributed execution
- Spark support
- Kubernetes orchestration
- Streaming pipelines
- Enterprise permissions
- Complex scheduling
- Dozens of connectors
- Multi-tenant SaaS architecture
- Real-time collaborative editing

## Initial Tech Stack

### Backend

- Python 3.11+
- FastAPI
- Pydantic v2
- SQLAlchemy 2.x
- Alembic
- Pandas
- Optional future dataframe engines:
  - Polars
  - DuckDB
  - Dask

### Frontend

- React
- TypeScript
- Vite
- @xyflow/react for visual flow editor
- TanStack Query for API state
- Zustand for lightweight client state
- shadcn/ui for UI components
- Tailwind CSS
- React Hook Form + Zod for forms and validation

### Database

Use SQLAlchemy as the abstraction layer.

Default local development database:
- PostgreSQL

Supported later through SQLAlchemy URLs:
- PostgreSQL
- MySQL/MariaDB
- SQL Server
- Others supported by SQLAlchemy dialects

The app must not hardcode database-specific behavior unless isolated behind adapters.

## Development Principles

1. Keep the MVP small.
2. Prefer explicit code over clever abstractions.
3. Every visual ETL node should map to a clear Python/pandas operation.
4. The generated Python code should be readable and educational.
5. Backend logic is the source of truth.
6. The frontend should validate early, but backend must validate everything again.
7. Avoid vendor lock-in.
8. Keep the app easy to run locally.
9. Design for extension, but do not over-engineer.
10. Every new transformation must include tests.

## Recommended Repository Structure

```text
etl-visual/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── routes/
│   │   │   │   ├── flows.py
│   │   │   │   ├── datasets.py
│   │   │   │   ├── runs.py
│   │   │   │   └── transformations.py
│   │   │   └── deps.py
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── database.py
│   │   │   └── logging.py
│   │   ├── db/
│   │   │   ├── models/
│   │   │   │   ├── flow.py
│   │   │   │   ├── dataset.py
│   │   │   │   └── run.py
│   │   │   └── repositories/
│   │   ├── schemas/
│   │   │   ├── flow.py
│   │   │   ├── dataset.py
│   │   │   └── run.py
│   │   ├── services/
│   │   │   ├── flow_service.py
│   │   │   ├── execution_service.py
│   │   │   ├── preview_service.py
│   │   │   └── codegen_service.py
│   │   ├── engine/
│   │   │   ├── graph.py
│   │   │   ├── registry.py
│   │   │   ├── executor.py
│   │   │   └── transformations/
│   │   │       ├── base.py
│   │   │       ├── clean.py
│   │   │       ├── reshape.py
│   │   │       ├── join.py
│   │   │       └── aggregate.py
│   │   └── main.py
│   ├── alembic/
│   ├── tests/
│   ├── pyproject.toml
│   ├── alembic.ini
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   ├── components/
│   │   │   ├── ui/
│   │   │   ├── flow/
│   │   │   └── layout/
│   │   ├── features/
│   │   │   ├── flows/
│   │   │   ├── datasets/
│   │   │   ├── runs/
│   │   │   └── transformations/
│   │   ├── lib/
│   │   │   ├── api.ts
│   │   │   ├── queryClient.ts
│   │   │   └── validators.ts
│   │   ├── stores/
│   │   └── main.tsx
│   ├── package.json
│   └── vite.config.ts
├── docs/
│   ├── architecture.md
│   ├── transformations.md
│   └── roadmap.md
├── docker-compose.yml
├── README.md
└── CLAUDE.md
```

## Core Domain Model

### Flow

A saved ETL pipeline.

Fields:
- id
- name
- description
- graph_json
- created_at
- updated_at

### Dataset

A data source or uploaded file.

Fields:
- id
- name
- source_type
- location
- schema_json
- sample_json
- created_at
- updated_at

### FlowRun

A single execution of a flow.

Fields:
- id
- flow_id
- status
- input_dataset_id
- output_location
- started_at
- finished_at
- error_message
- logs_json

### Transformation Node

A visual node in the graph.

Fields:
- id
- type
- label
- config
- position
- input_handles
- output_handles

## MVP Node Types

### Input Nodes

- CSV input
- Excel input
- Parquet input

### Cleaning Nodes

- Rename columns
- Drop columns
- Filter rows
- Fill null values
- Drop null values
- Remove duplicates
- Change data types
- Sort rows
- Add new calculated columns

### Transform Nodes

- Select columns
- Create calculated column
- Group by + aggregate
- Join/merge
- Union/concat

### Output Nodes

- CSV output
- Excel output
- Parquet output

## API Design

Use REST first. Avoid GraphQL for MVP.

### Flow endpoints

- `GET /api/flows`
- `POST /api/flows`
- `GET /api/flows/{flow_id}`
- `PUT /api/flows/{flow_id}`
- `DELETE /api/flows/{flow_id}`

### Preview endpoints

- `POST /api/flows/{flow_id}/preview`
- `POST /api/transformations/preview`

### Run endpoints

- `POST /api/flows/{flow_id}/runs`
- `GET /api/runs/{run_id}`

### Dataset endpoints

- `POST /api/datasets/upload`
- `GET /api/datasets`
- `GET /api/datasets/{dataset_id}/sample`
- `GET /api/datasets/{dataset_id}/schema`

### Code generation

- `POST /api/flows/{flow_id}/export/python`

## Execution Engine

The execution engine should:

1. Receive graph JSON from the saved flow.
2. Validate graph structure.
3. Topologically sort nodes.
4. Load input datasets.
5. Execute transformation nodes in order.
6. Store or return output.
7. Save run metadata and errors.
8. Generate readable logs.

Each transformation should implement a shared interface.

Example:

```python
class Transformation:
    type: str

    def validate_config(self, config: dict) -> None:
        ...

    def execute(self, df, config: dict):
        ...

    def to_python_code(self, input_var: str, output_var: str, config: dict) -> str:
        ...
```

## Graph JSON Shape

Prefer a format compatible with React Flow.

```json
{
  "nodes": [
    {
      "id": "input_1",
      "type": "csvInput",
      "position": { "x": 100, "y": 100 },
      "data": {
        "label": "CSV Input",
        "config": {
          "dataset_id": "dataset_123"
        }
      }
    }
  ],
  "edges": [
    {
      "id": "edge_1",
      "source": "input_1",
      "target": "drop_nulls_1"
    }
  ]
}
```

## Backend Coding Standards

- Use type hints everywhere.
- Use Pydantic schemas for API inputs and outputs.
- Keep route handlers thin.
- Put business logic in services.
- Put dataframe transformation logic in `app/engine`.
- Do not import FastAPI inside the dataframe engine.
- Do not mix ORM models and Pydantic schemas.
- Do not use pandas directly in API route files.
- Add tests for each transformation.

## Frontend Coding Standards

- Use TypeScript.
- Use feature-based folders.
- Keep React Flow-specific logic inside `components/flow` or `features/flows`.
- Use TanStack Query for server state.
- Use Zustand only for local UI/editor state.
- Use shadcn/ui for buttons, dialogs, forms, tabs, alerts, dropdowns, and cards.
- Validate node config forms with Zod.
- Keep API calls centralized in `lib/api.ts`.

## MVP Screens

1. Home / Flow list
2. Flow editor
3. Dataset upload
4. Node config sidebar
5. Data preview panel
6. Run history panel
7. Export Python code modal

## Suggested First Milestone

Build a vertical slice:

1. Upload CSV.
2. Display schema and sample.
3. Create a flow with:
   - CSV input
   - Drop nulls
   - Rename columns
   - CSV output
4. Preview each transformation.
5. Run the full flow.
6. Export generated Python script.

## Testing Strategy

Backend:
- Unit tests for transformations.
- Unit tests for graph validation.
- API tests for flow CRUD.
- Integration test for one full CSV pipeline.

Frontend:
- Component tests for node config forms.
- Basic flow editor tests.
- API mocking for editor interactions.

## Naming Guidelines

Use clear names.

Good:
- `DropNullsTransformation`
- `RenameColumnsTransformation`
- `FlowExecutionService`
- `TransformationRegistry`

Avoid:
- `Processor`
- `Manager`
- `Handler`
- `Thing`
- Overly generic abstractions

## Claude Code Instructions

When implementing this project:

1. Start with the smallest working vertical slice.
2. Do not introduce infrastructure before it is needed.
3. Prefer SQLite as the default database.
4. Make database URL configurable through environment variables.
5. Use SQLAlchemy and Alembic for persistence.
6. Keep generated Python code readable.
7. Avoid premature optimization.
8. Add tests when adding transformations.
9. Update documentation when architecture changes.
10. Ask before adding large dependencies.

## Definition of Done for MVP

The MVP is complete when a user can:

1. Start backend and frontend locally.
2. Upload a CSV file.
3. Build a simple ETL graph visually.
4. Configure at least five transformations.
5. Preview intermediate data.
6. Execute the full flow.
7. Download/export the output file.
8. Export equivalent Python/pandas code.
