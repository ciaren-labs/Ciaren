---
title: Projects API
description: Manage workspaces that group datasets and flows
search: api projects workspace crud default
---

# Projects API

Lightweight workspaces that group related datasets and flows. A `Default`
project is created automatically; every dataset and flow belongs to one.

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/projects` | List projects (with dataset/flow counts) |
| `POST` | `/api/projects` | Create a project |
| `GET` | `/api/projects/{project_id}` | Get one project |
| `PUT` | `/api/projects/{project_id}` | Update a project |
| `DELETE` | `/api/projects/{project_id}` | Delete a project (its items move to `Default`) |

Deleting a project never deletes its datasets or flows — they're reassigned to
the `Default` project.

## See also

- [Datasets API](./datasets.md) · [Flows API](./flows.md)
- [Projects & Runs](/guide/projects-and-runs)
