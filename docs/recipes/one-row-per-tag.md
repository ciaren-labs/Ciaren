---
title: One Row per Tag While Preserving Record IDs
description: Split a delimited tags column into one row per tag in Ciaren with Split to Rows, repeat the record ID on every row, trim stray spaces, and handle null and empty tags. Includes the pandas and Polars export.
search: recipe split rows tags delimiter record id explode one row per value pandas polars null empty
---

# One Row per Tag While Preserving Record IDs

Each article has a `tags` field such as `news;sports`, and you want one row per
tag so you can count or join on tags. **Split to Rows** splits the text and
gives each piece its own row, repeating the other columns. It adds rows;
[Split a Column](/recipes/split-a-column) adds columns instead.

**You'll use:** [File Input](/transformations/file-input) →
[Split to Rows](/transformations/split-to-rows) →
[String Transform](/transformations/string-transform) →
[File Output](/transformations/file-output).

<FlowPipeline :nodes='[
  {"type":"input","label":"File Input","detail":"articles.csv"},
  {"type":"transform","label":"Split to Rows","detail":"tags · delimiter ;"},
  {"type":"transform","label":"String Transform","detail":"tags · Strip spaces"},
  {"type":"output","label":"File Output","detail":"article_tags"}
]' />

## Sample data

Save this as `articles.csv`. Record `r3` has no tags, `r4` ends with a
delimiter, and `r5` has a space after the delimiter.

```csv
record_id,tags
r1,news;sports
r2,news
r3,
r4,a;
r5,news; sports
```

## Steps

1. On **Datasets**, upload `articles.csv`.
2. In a new flow, add **File Input**. Set **File type** to CSV and **Dataset**
   to `articles.csv`.
3. Add **Split to Rows**. Set **Column** to `tags` and **Delimiter (optional)**
   to `;`.
4. Add **String Transform**. Set **Column** to `tags` and click **Strip
   spaces**. Without it, `r5` gets the tag `" sports"`, which does not match
   `sports`.
5. Add **File Output**. Set **File type** to CSV (.csv) and **Dataset name** to
   `article_tags`. Connect the nodes in order and click **Run**.

![Split to Rows turns five records into eight rows: each tag gets its own row with the record_id repeated, a null stays one null row, a trailing delimiter adds an empty tag, and a space after the delimiter stays in the tag](/illustrations/recipes/split-to-rows-fanout.svg)

:::tip Prefer to describe it?
With a provider key set up, upload the sample data, open a blank flow in the same project and ask the [Flow assistant](/guide/flow-assistant), for example: "split the tags column on semicolons into one row per tag." Review the proposed nodes and settings, then choose **Apply and save**. The manual steps above build the same flow. The assistant never runs a flow, so click **Run** yourself.
:::

## Result

Five records become eight rows:

| record_id | tags |
| --- | --- |
| r1 | news |
| r1 | sports |
| r2 | news |
| r3 | null |
| r4 | a |
| r4 | empty text (`""`) |
| r5 | news |
| r5 | sports |

## Check the result

Save the flow, click **Preview**, select the String Transform node and click
**Run preview**. You should see 8 rows, with `r1` and `r5` on two rows each.
Switch to **Profile**: `tags` should list `news` 3 times and `sports` 2 times.
If `sports` appears only once, the Strip spaces step is missing.

## Pitfalls

- **A null stays one row.** `r3` keeps one row with a null tag, so the record
  does not disappear.
- **A trailing delimiter adds an empty tag.** `a;` gives `a` and an empty text.
  Remove such rows with [Filter by Expression](/transformations/filter-expression),
  for example `tags != ''`, which drops the empty tag and keeps the null row.
- **Null and empty text look alike in a CSV.** Both are written as an empty
  cell by the pandas engine; Polars writes the empty text as `""`. Check the
  preview, not the file.
- **Pick the delimiter the data uses.** With the default `,`, nothing in this
  sample is split.

## Exported Python

Click **Export** in the editor toolbar. The **pandas** and **polars** tabs show
this code for the flow. It reads `articles.csv` from the script's folder and
writes `article_tags.csv`.

::: code-group

```python [pandas]
import pandas as pd

df_articles = pd.read_csv('articles.csv')

df_articles = (
    df_articles.assign(tags=lambda _d: _d['tags'].astype('string').str.split(';'))
    .explode('tags')
    .reset_index(drop=True)
    .assign(tags=lambda _d: _d['tags'].astype('string').str.strip())
)

df_articles.to_csv('article_tags.csv', index=False)
```

```python [Polars]
import polars as pl

df_articles = pl.read_csv('articles.csv')

df_articles = (
    df_articles.with_columns(pl.col('tags').cast(pl.Utf8).str.split(';'))
    .explode('tags')
    .with_columns(pl.col('tags').cast(pl.Utf8).str.strip_chars())
)

df_articles.write_csv('article_tags.csv')
```

:::

## See also

- [Split to Rows](/transformations/split-to-rows)
- [Split a Column](/recipes/split-a-column)
- [Recipes](/recipes/overview)
