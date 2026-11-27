---
title: Fill Missing Values
description: "Replace missing values in Ciaren with the Fill Nulls node: a median for a numeric column, a constant for a text column, and forward or backward fill for ordered data."
search: recipe fill missing values nulls nan impute mean median mode constant forward fill backward fill
---

# Fill Missing Values

A survey export has empty cells in `age` and `region`, and you want to keep
every respondent instead of dropping rows. Use one **Fill Nulls** node per
column group: the median for `age`, the text `Unknown` for `region`.

**You'll use:** [File Input](/transformations/file-input) →
[Fill Nulls](/transformations/fill-nulls) → Fill Nulls →
[File Output](/transformations/file-output).

<FlowPipeline :nodes='[
  {"type":"input","label":"File Input","detail":"survey.csv"},
  {"type":"clean","label":"Fill Nulls","detail":"age → median"},
  {"type":"clean","label":"Fill Nulls","detail":"region → Unknown"},
  {"type":"output","label":"File Output","detail":"survey_filled"}
]' />

## Sample data

Save this as `survey.csv`. Respondent 2 has no age and respondent 3 has no
region. An empty cell in a CSV is read as null.

```csv
respondent_id,age,region
1,25,North
2,,South
3,40,
4,31,East
5,95,North
```

## Steps

1. On **Datasets**, upload `survey.csv`.
2. In a new flow, add **File Input**. Set **File type** to CSV and **Dataset**
   to `survey.csv`.
3. Add **Fill Nulls**. Set **Strategy** to Median and **Columns (optional)** to
   `age`.
4. Add a second **Fill Nulls**. Set **Strategy** to Constant value, **Fill
   value** to `Unknown`, and **Columns (optional)** to `region`. Each node has
   one strategy, so a second column that needs a different fill needs a second
   node.
5. Add **File Output**. Set **File type** to CSV (.csv) and **Dataset name** to
   `survey_filled`. Connect the nodes in order and click **Run**.

## Result

| respondent_id | age | region |
| --- | --- | --- |
| 1 | 25.0 | North |
| 2 | **35.5** | South |
| 3 | 40.0 | **Unknown** |
| 4 | 31.0 | East |
| 5 | 95.0 | North |

The median of 25, 31, 40 and 95 is 35.5. The filled value is a decimal, so the
whole `age` column is written with decimals.

## Choose the strategy

![The age column has one null and one outlier, 95: the mean fills 47.75 in Ciaren runs (47 in the exported Polars script), the median fills 35.5](/illustrations/recipes/fill-nulls-mean-median.svg)

- **Median** is the safer default for numbers with outliers. On this sample the
  mean would fill 47.75, older than three of the four known ages. That is the
  value in Ciaren runs on either engine. The exported Polars script reads `age`
  from your CSV as integers and writes 47; the median does not have this
  problem.
- **Mean (average)**, **Minimum**, **Maximum** and **Zero** also fill numeric
  columns. **Most frequent (mode)** works for text too.
- **Forward fill** copies the value from the row above, **Backward fill** from
  the row below. Use them only on data in a meaningful order, such as a time
  series sorted by date. On this sample, forward fill would give respondent 3
  the region `South` from respondent 2.

## Check the result

Save the flow, click **Preview**, select the second Fill Nulls node and click
**Run preview**. Respondent 2 should show age `35.5` and respondent 3 region
`Unknown`. Switch to **Profile**: the null count for `age` and `region` should
be 0.

## Pitfalls

- **Set the columns.** With **Columns (optional)** empty, a constant like
  `Unknown` goes into every text column that has a null, not only `region`.
- **A space is not missing.** A cell that contains only spaces is text, not
  null, so Fill Nulls leaves it alone. Fix such cells in the source file, where
  an empty cell is read as null.
- **Filling before training a model** computes the median on all rows,
  including the rows you later test on. For modeling, use the train node's
  **Advanced → Preprocessing** options instead, see
  [Feature Engineering](/examples/feature-engineering).
- **To drop the rows instead**, use [Drop Nulls](/transformations/drop-nulls).

## Exported Python

Click **Export** in the editor toolbar. The **pandas** and **polars** tabs show
this code for the flow. It reads `survey.csv` from the script's folder and
writes `survey_filled.csv`.

::: code-group

```python [pandas]
import pandas as pd

df_survey = pd.read_csv('survey.csv')

df_survey = (
    df_survey.fillna({'age': df_survey['age'].median()})
    .fillna({'region': 'Unknown'})
)

df_survey.to_csv('survey_filled.csv', index=False)
```

```python [Polars]
import polars as pl

df_survey = pl.read_csv('survey.csv')

df_survey = (
    df_survey.with_columns(pl.col('age').fill_null(pl.col('age').median()))
    .with_columns(pl.col('region').fill_null('Unknown'))
)

df_survey.write_csv('survey_filled.csv')
```

:::

## See also

- [Fill Nulls](/transformations/fill-nulls)
- [Drop Nulls](/transformations/drop-nulls)
- [Combine Columns with Fallback Values](/recipes/coalesce-fallback-values)
- [Recipes](/recipes/overview)
