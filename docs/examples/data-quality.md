---
title: Data Quality Checks
description: "Ciaren example: clean a messy contact list by trimming text, coercing types, dropping nulls and duplicates, and filtering out-of-range ages, in an order that keeps the right rows."
search: example data quality validation clean duplicates outliers coerce strip lowercase
---

# Data Quality Checks

A contact export has stray spaces, mixed-case emails, a non-numeric age, a
duplicate person, an impossible age and a row with no name. This flow fixes what
can be fixed, drops what cannot, and leaves two trustworthy rows. The order of
the steps matters, and the figure below shows why.

**You'll use:** File Input → String Transform (three times) → Change Types →
Drop Nulls → Remove Duplicates → Filter by Expression → File Output.

<FlowPipeline :nodes='[
  {"type":"input","label":"File Input","detail":"contacts.csv"},
  {"type":"clean","label":"String Transform","detail":"name: strip whitespace"},
  {"type":"clean","label":"String Transform","detail":"email: strip whitespace"},
  {"type":"clean","label":"String Transform","detail":"email: lowercase"},
  {"type":"clean","label":"Change Types","detail":"age → integer, bad values → null"},
  {"type":"clean","label":"Drop Nulls","detail":"subset: name, age"},
  {"type":"clean","label":"Remove Duplicates","detail":"subset: email · keep: first"},
  {"type":"clean","label":"Filter by Expression","detail":"age between 0 and 120"},
  {"type":"output","label":"File Output","detail":"contacts_clean.csv"}
]' :vertical="true" />

## Sample data

Save this as `contacts.csv`, or [download contacts.csv](/samples/data-quality/contacts.csv),
and upload it on the **Datasets** page:

```csv
name,email,age
  Ada Lovelace ,ADA@EXAMPLE.COM,36
Grace Hopper,grace@example.com,unknown
Grace Hopper,GRACE@EXAMPLE.COM,85
Linus T,linus@example.com ,250
,bad-row@example.com,40
```

What is wrong with each row:

| Row | Problem |
| --- | --- |
| Ada | Spaces around the name, uppercase email |
| Grace (1st) | Age is the text `unknown` |
| Grace (2nd) | Same person as the first Grace, email in uppercase |
| Linus | Trailing space in the email, age 250 |
| (no name) | Empty name |

## Build the flow

1. **File Input**: **File type** CSV, dataset `contacts.csv`.
2. **String Transform**: **Column** `name`, **Operation** *Strip spaces*.
3. **String Transform**: **Column** `email`, **Operation** *Strip spaces*.
4. **String Transform**: **Column** `email`, **Operation** *Lowercase*.
   After steps 3 and 4, `GRACE@EXAMPLE.COM` and `grace@example.com` are the same
   string, so the duplicate check in step 7 can see them.
5. **Change Types**: under **Casts**, set `age` → `integer`. Set
   **On bad values** to *Set to null (coerce)*. `unknown` becomes null instead of
   stopping the run.
6. **Drop Nulls**: **Subset** = `name`, `age`. This removes the row with no name
   (an empty CSV cell reads as null) and the first Grace, whose age is now null.
7. **Remove Duplicates**: **Subset** = `email`, **Keep** *first occurrence*.
   Only one `grace@example.com` row is left by now, so nothing else is removed
   here on this sample; on real data, this is where repeats of the same person
   go.
8. **Filter by Expression**: type `age >= 0 and age <= 120` into
   **Expression**, or use **Build condition** with `age`,
   **between (range)**, `0` and `120`, then click **Use condition**. Both bounds
   are inclusive. This drops Linus's age of 250.
9. **File Output**: **File type** CSV, **Dataset name** `contacts_clean`.

Select steps 5 to 8 one at a time and read the preview to see each rule remove
exactly the row you expect.

## Why Drop Nulls comes before Remove Duplicates

Both Grace rows share an email. *Keep first occurrence* keeps whichever comes
first, and the first one is the copy with the unusable age. If you remove
duplicates before you drop nulls, that bad copy wins, the good copy is
discarded, and Drop Nulls then removes the bad copy too. Grace disappears from
the output.

![Removing duplicates first keeps the Grace row with a null age, which Drop Nulls then deletes; dropping nulls first leaves the Grace row with age 85](/illustrations/examples/quality-step-order.svg)

The same logic applies to the String Transform steps: lowercase before you
deduplicate, or `GRACE@EXAMPLE.COM` and `grace@example.com` count as two people.

## Result

<DataTransform
  transform="Full flow"
  :before='{
    "columns":["name","email","age"],
    "rows":[
      ["  Ada Lovelace ","ADA@EXAMPLE.COM","36"],
      ["Grace Hopper","grace@example.com","unknown"],
      ["Grace Hopper","GRACE@EXAMPLE.COM","85"],
      ["Linus T","linus@example.com ","250"],
      [null,"bad-row@example.com","40"]
    ]
  }'
  :after='{
    "columns":["name","email","age"],
    "rows":[
      ["Ada Lovelace","ada@example.com",36],
      ["Grace Hopper","grace@example.com",85]
    ]
  }'
  :highlight='["name","email","age"]'
/>

### Check the result

- Two rows: Ada Lovelace, 36, and Grace Hopper, 85.
- `ada@example.com` is lowercase and `Ada Lovelace` has no leading space.
- The preview of Change Types shows `age` as an integer column with one empty
  cell, for the first Grace.

If Grace is missing, Remove Duplicates runs before Drop Nulls. If Ada's email
is still `ADA@EXAMPLE.COM`, the Lowercase step is missing or set on the wrong
column.

## Exported Python

Click **Export** in the editor toolbar and open the **pandas** tab:

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
    .query('age >= 0 and age <= 120')
    .reset_index(drop=True)
)

df_contacts.to_csv('contacts_clean.csv', index=False)
```

Run it next to `contacts.csv` and `contacts_clean.csv` holds the same two rows.
`Int64` (capital I) is pandas' nullable integer type: it can hold the null that
`errors='coerce'` produces, which plain `int64` cannot. The **polars** tab
writes the same rows; its filter step converts the frame to pandas to evaluate
the expression, so it needs pandas and PyArrow installed next to polars.

## Pitfalls

- **Coerce hides bad values.** *Set to null (coerce)* turns anything unparseable
  into null without an error. Here Drop Nulls removes those rows right after, so
  check the Change Types preview to see how many there were.
- **Drop Nulls with an empty subset checks every column.** Set the subset to
  the columns that must be present; a missing optional column should not cost
  you the row.
- **Remove Duplicates without a subset compares whole rows.** The two Graces
  differ in `age`, so they would both survive.

## Going further

- **Fail instead of filtering.** Replace Filter by Expression with **Assert Value Range**
  (**Column** `age`, **Min** `0`, **Max** `120`, **On violation**
  *Error (stop run)*) when an impossible age should stop the pipeline rather
  than disappear quietly.
- **Check email format.** Add a **Filter Rows** with **Operator**
  *contains (text)* and **Value** `@`.
- **Keep the table fresh.** [Schedule](/guide/scheduling) the flow to rerun on
  each new export.

## Next steps

- [Sales Data Analysis](/examples/sales-analysis)
- [Remove Duplicates reference](/transformations/remove-duplicates)
- [Transformations Reference](/transformations/overview)
