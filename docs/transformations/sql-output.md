---
title: SQL output
search: sql output database table write connection if_exists append replace
description: Write the result of a flow to a database table via a reusable connection
---

# SQL output — `sqlOutput`

Write the result to a database table via a reusable
[Connection](/guide/connections).

<FlowPipeline
  :nodes='[
    {"type":"input","label":"SQL Input","detail":"raw orders"},
    {"type":"clean","label":"Drop Nulls"},
    {"type":"transform","label":"Calculated Column","detail":"total = price × qty"},
    {"type":"output","label":"SQL Output","detail":"cleaned_orders — append"}
  ]'
/>

## Use cases

- Land a cleaned dataset into an analytics table on a schedule.
- Append daily results to a growing table, or replace a table each run.

## Configuration

| Config key | Type | Required | Description |
| --- | --- | --- | --- |
| `connection_id` | string | Yes | The connection to write to |
| `table` | string | Yes | Target table |
| `schema` | string | No | Schema to write into |
| `if_exists` | string | No | `replace` (default), `append`, or `fail` |

## Generated Python code

```python
df_5.to_sql("cleaned_orders", _engine_1, if_exists="replace", index=False)
```

::: tip Security
Exported code never embeds the password — it resolves the connection's secret
reference at runtime (`os.environ[...]` for `env:`/bare names,
`keyring.get_password(...)` for `keyring:NAME`, or a `file:/path` read for a
mounted secret file). See [Connections](/guide/connections).
:::

## Tips & common mistakes

- **`replace` drops and recreates** the table (and its schema/indexes). Use
  `append` to keep an existing table and add rows; `fail` to abort if it exists.
- **Match the table's columns.** With `append`, the frame's columns should line
  up with the target table.

## See also

- [SQL input](./sql-input.md)
- [Database Connections](/guide/connections)
- [Connections API](/api/connections)
