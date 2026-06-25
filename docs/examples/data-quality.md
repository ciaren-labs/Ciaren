---
title: Data Quality Checks
description: Standardize messy records, coerce types, and drop bad rows
search: example data quality validation clean duplicates outliers coerce
---

# Data Quality Checks

Real-world files are messy: stray whitespace, inconsistent casing, junk in
numeric columns, duplicates, and out-of-range values. This flow standardizes a
contact list and drops the rows that can't be trusted.

**You'll use:** CSV Input → String Transform → Cast Types → Drop Nulls →
Remove Duplicates → Filter Rows → CSV Output.

## Sample data

`contacts.csv`:

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

1. **CSV Input** — select `contacts.csv`.
2. **String Transform** — `column: "name"`, `operation: "strip"` (trim whitespace).
3. **String Transform** — `column: "email"`, `operation: "strip"`.
4. **String Transform** — `column: "email"`, `operation: "lower"` (normalize case
   so duplicates collapse).
5. **Cast Types** — `casts: { "age": "integer" }`, `errors: "coerce"`. Non-numeric
   ages (like `"unknown"`) become null instead of erroring.
6. **Drop Nulls** — `subset: ["name", "age"]`. This removes the no-name row and the
   row whose age couldn't be parsed. (Empty strings from the file read as null.)
7. **Remove Duplicates** — `subset: ["email"]`, `keep: "first"`. Now that emails are
   normalized, the duplicate Grace collapses to one row.
8. **Filter Rows** — `column: "age"`, `operator: "between"`, `value: 0`,
   `value2: 120` (drop the impossible 250).
9. **CSV Output** — `path: "contacts_clean.csv"`.

Watch the **live preview** at steps 5–8 to confirm each rule does what you expect.

## Exported Python

```python
import pandas as pd

df_1 = pd.read_csv("contacts.csv")
df_2 = df_1.assign(**{'name': df_1['name'].astype('string').str.strip()})
df_3 = df_2.assign(**{'email': df_2['email'].astype('string').str.strip()})
df_4 = df_3.assign(**{'email': df_3['email'].astype('string').str.lower()})
df_5 = df_4.assign(**{'age': pd.to_numeric(df_4['age'], errors='coerce').astype('Int64')})
df_6 = df_5.dropna(subset=['name', 'age'])
df_7 = df_6.drop_duplicates(subset=['email'], keep='first')
df_8 = df_7[df_7['age'].between(0, 120)]
df_8.to_csv("contacts_clean.csv", index=False)
```

## Result

| name | email | age |
| ------ | ------- | ----- |
| Ada Lovelace | `ada@example.com` | 36 |
| Grace Hopper | `grace@example.com` | 85 |

Ada and Grace survive; the unparseable age, the no-name row, the duplicate, and
the age-250 row are all gone.

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
