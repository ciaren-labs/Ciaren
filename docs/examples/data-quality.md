---
title: Data Quality Checks
description: Standardize messy records, coerce types, and drop bad rows
search: example data quality validation clean duplicates outliers coerce
---

# Data Quality Checks

Real-world files are messy: stray whitespace, inconsistent casing, junk in
numeric columns, duplicates, and out-of-range values. This flow standardizes a
contact list and drops the rows that can't be trusted.

**You'll use:** File Input → String Transform → Change Types → Drop Nulls →
Remove Duplicates → Filter Rows → File Output.

<FlowPipeline :nodes='[
  {"type":"input","label":"File Input","detail":"contacts.csv"},
  {"type":"clean","label":"String Transform","detail":"strip whitespace from name"},
  {"type":"clean","label":"String Transform","detail":"strip + lowercase email"},
  {"type":"clean","label":"Change Types","detail":"age→integer, errors=coerce → nulls"},
  {"type":"clean","label":"Drop Nulls","detail":"subset: name, age"},
  {"type":"clean","label":"Remove Duplicates","detail":"subset: email · keep: first"},
  {"type":"clean","label":"Filter Rows","detail":"0 ≤ age ≤ 120"},
  {"type":"output","label":"File Output","detail":"contacts_clean.csv"}
]' />

## Sample data

`contacts.csv` (📥 [download contacts.csv](/samples/data-quality/contacts.csv)):

```csv
name,email,age
  Ada Lovelace ,ADA@EXAMPLE.COM,36
Grace Hopper,grace@example.com,unknown
Grace Hopper,GRACE@EXAMPLE.COM,85
Linus T,linus@example.com ,250
,bad-row@example.com,40
```

Problems: leading/trailing spaces, mixed-case emails, a non-numeric age, a
duplicate person (same email, different casing), an impossible age (250), and a
row with no name.

## Build the flow

1. **File Input** — File type CSV, select `contacts.csv`.
2. **String Transform** — `column: "name"`, `operation: "strip"` (trim whitespace).
3. **String Transform** — `column: "email"`, `operation: "strip"`.
4. **String Transform** — `column: "email"`, `operation: "lower"` (normalize case
   so duplicates collapse).
5. **Change Types** — `casts: { "age": "integer" }`, `errors: "coerce"`. Non-numeric
   ages (like `"unknown"`) become null instead of erroring.
6. **Drop Nulls** — `subset: ["name", "age"]`. This removes the no-name row and the
   row whose age couldn't be parsed. (Empty strings from the file read as null.)
7. **Remove Duplicates** — `subset: ["email"]`, `keep: "first"`. Now that emails are
   normalized, the duplicate Grace collapses to one row.
8. **Filter Rows** — `column: "age"`, `operator: "between"`, `value: 0`,
   `value2: 120` (drop the impossible 250).
9. **File Output** — `format: csv` (name `contacts_clean`).

Watch the **live preview** at steps 5–8 to confirm each rule does what you expect.

## Exported Python

```python
import pandas as pd

df_contacts = pd.read_csv('contacts.csv')

df_contacts = (
    df_contacts.assign(name=lambda _d: _d['name'].astype('string').str.strip())
    .assign(email=lambda _d: _d['email'].astype('string').str.strip())
    .assign(email=lambda _d: _d['email'].astype('string').str.lower())
    .assign(age=lambda _d: pd.to_numeric(_d['age'], errors='coerce').astype('Int64'))
    .dropna(subset=['name', 'age'])
    .drop_duplicates(subset='email')
    .loc[lambda _d: _d['age'].between(0, 120)]
)

df_contacts.to_csv('contacts_clean.csv', index=False)
```

## Result

Starting from 5 raw rows with 5 distinct quality issues, the pipeline reduces
to 2 clean, trustworthy records.

<DataTransform
  transform="Full pipeline"
  :before='{
    "columns":["name","email","age"],
    "rows":[
      ["  Ada Lovelace ","ADA@EXAMPLE.COM",36],
      ["Grace Hopper","grace@example.com","unknown"],
      ["Grace Hopper","GRACE@EXAMPLE.COM",85],
      ["Linus T","linus@example.com ",250],
      [null,"bad-row@example.com",40]
    ]
  }'
  :after='{
    "columns":["name","email","age"],
    "rows":[
      ["Ada Lovelace","ada@example.com",36],
      ["Grace Hopper","grace@example.com",85]
    ]
  }'
/>

Ada and Grace survive. Dropped: the unparseable age (`unknown` → null), the
no-name row, the duplicate Grace (same normalised email), and the impossible age
of 250.

## Going further

- **Catch outliers instead of guessing bounds.** Swap the Filter for a
  **Remove Outliers** node (`method: "iqr"`, `action: "drop"`) to drop statistical
  outliers in `age` automatically.
- **Validate formats.** Use **Filter Rows** with `operator: "contains"` and
  `value: "@"` to drop rows with malformed emails.
- **Run it on a schedule.** Point this flow at a folder export and
  [schedule it](/guide/scheduling) to keep a clean table up to date.

## Next steps

- [Transformations Reference](/transformations/overview)
- [Sales Data Analysis](/examples/sales-analysis)
