---
title: Feature Engineering
description: "Ciaren example: prepare ML features visually. Fill a missing income, one-hot encode a region, scale numeric columns, keep the most relevant features and compress two of them with PCA."
search: example feature engineering scale encode one-hot select features kbest pca dimensionality reduction sklearn
---

# Feature Engineering

Before you train a model, the raw columns usually need reshaping: a missing
value filled, a text category turned into numbers, columns on very different
scales brought to one scale. This walkthrough runs those steps on six loan
applicants, then keeps the two most relevant numeric features and compresses
them into one principal component. Every node previews its output, so you can
watch the table change shape.

**You'll use:** File Input → Fill Nulls → Encode Categories → Scale Features →
Select Features → Reduce Dimensions → File Output.

<FlowPipeline :nodes='[
  {"type":"input","label":"File Input","detail":"applicants.csv"},
  {"type":"clean","label":"Fill Nulls","detail":"income → median"},
  {"type":"ml","label":"Encode Categories","detail":"one-hot: region"},
  {"type":"ml","label":"Scale Features","detail":"standard: age, income, score"},
  {"type":"ml","label":"Select Features","detail":"top 2 by relevance to approved"},
  {"type":"ml","label":"Reduce Dimensions","detail":"PCA: age, score → pc_1"},
  {"type":"output","label":"File Output","detail":"features.csv"}
]' :vertical="true" />

## Sample data

Save this as `applicants.csv`, or [download applicants.csv](/samples/feature-engineering/applicants.csv),
and upload it on the **Datasets** page:

```csv
applicant_id,age,income,region,score,approved
1,25,42000,North,0.61,0
2,41,88000,South,0.82,1
3,33,,North,0.55,0
4,52,120000,East,0.91,1
5,29,51000,South,0.64,0
6,46,99000,East,0.88,1
```

`approved` is the target you would later predict. Applicant 3 has no income.

## Build the flow

1. **File Input**: **File type** CSV, dataset `applicants.csv`.
2. **Fill Nulls**: **Strategy** *Median*, **Columns** `income`. The median of
   the five known incomes is 88000, so applicant 3 gets 88000. *Mean (average)*
   would fill 80000 instead; the median moves less when one income is extreme.
3. **Encode Categories**: **Method** *One-hot (dummy columns)*, **Columns**
   `region`. `region` is replaced by `region_East`, `region_North` and
   `region_South`, each true or false.
4. **Scale Features**: **Method** *Standard (z-score)*, **Columns** `age`,
   `income`, `score`. Each column becomes "standard deviations from its mean".
5. **Select Features**: **Method** *Top-K by relevance*, **Target column**
   `approved`, **Keep top K** `2`. It scores every numeric column except the
   target and keeps the two strongest: `score` and `age`. `income` and
   `applicant_id` are dropped.
6. **Reduce Dimensions**: **Components** `1`, **Columns** `age`, `score`,
   **Component prefix** `pc`, **Random seed** `42`. `age` and `score` are
   replaced by one column, `pc_1`.
7. **File Output**: **File type** CSV, **Dataset name** `features`.

Feature nodes do not end a flow, so the File Output is what lets you **Run** and
export it. You can also connect the last feature node to a **Train Classifier**
node instead.

:::tip Prefer to describe it?
With a provider key set up, upload the sample data, open a blank flow in the same project and ask the [Flow assistant](/guide/flow-assistant), for example: "fill nulls, one-hot encode the region, scale the numbers and reduce age and score to one component." Review the proposed nodes and settings, then choose **Apply and save**. The manual steps above build the same flow. The assistant never runs a flow, so click **Run** yourself.
:::

## What one-hot encoding does

A model cannot multiply the word `North`. One-hot encoding gives each region its
own column and marks the applicant's region as true. No region is ranked above
another, which an integer code (East = 0, North = 1, South = 2) would imply.

![One-hot encoding turns the region column into three true/false columns, region_East, region_North and region_South, with exactly one true per row](/illustrations/examples/features-one-hot.svg)

## What scaling does

Before scaling, `income` is in tens of thousands and `score` is below 1. Any
method that measures distance or variance, such as PCA, would see income
differences as thousands of times larger. Standard scaling subtracts each
column's mean and divides by its standard deviation, so all three columns are
centered on 0 with a spread of 1.

![Standard scaling maps age 25 to 52 and income 42000 to 120000 onto the same z-score axis, centered on 0](/illustrations/examples/features-scaling.svg)

<DataTransform
  transform="Scale Features (standard)"
  :before='{
    "columns":["age","income","score"],
    "rows":[[25,42000,0.61],[41,88000,0.82],[33,88000,0.55],[52,120000,0.91],[29,51000,0.64],[46,99000,0.88]]
  }'
  :after='{
    "columns":["age","income","score"],
    "rows":[[-1.33,-1.46,-0.89],[0.35,0.25,0.61],[-0.49,0.25,-1.32],[1.51,1.43,1.25],[-0.91,-1.12,-0.68],[0.88,0.66,1.04]]
  }'
  :highlight='["age","income","score"]'
/>

Values are rounded to two decimals here; the node keeps full precision. The
standard deviation is the population one (scikit-learn's `StandardScaler`), so
for `age` it is 9.52, not the 10.42 a spreadsheet's `STDEV` gives.

## Result

PCA finds the direction in which `age` and `score` vary together. The two are
strongly correlated in this sample (0.91), so one component keeps 95% of their
combined variance. With both columns scaled, `pc_1` is simply
(`age` + `score`) / √2 in z-scores.

<DataTransform
  transform="Full flow"
  :before='{
    "columns":["applicant_id","age","income","region","score","approved"],
    "rows":[
      [1,25,42000,"North",0.61,0],[2,41,88000,"South",0.82,1],[3,33,null,"North",0.55,0],
      [4,52,120000,"East",0.91,1],[5,29,51000,"South",0.64,0],[6,46,99000,"East",0.88,1]
    ]
  }'
  :after='{
    "columns":["approved","region_East","region_North","region_South","pc_1"],
    "rows":[
      [0,"False","True","False",-1.57],[1,"False","False","True",0.68],[0,"False","True","False",-1.28],
      [1,"True","False","False",1.95],[0,"False","False","True",-1.12],[1,"True","False","False",1.35]
    ]
  }'
  :highlight='["pc_1"]'
/>

### Check the result

- Five columns, six rows. `region` is gone and three `region_*` columns took its
  place.
- `pc_1` is negative for the three rejected applicants and positive for the
  three approved ones.
- In the Scale Features preview, each scaled column sums to 0 (up to rounding).

## Exported Python

Click **Export** in the editor toolbar and open the **pandas** tab:

```python
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.feature_selection import SelectKBest, f_classif, f_regression
from sklearn.preprocessing import StandardScaler

df_applicants = pd.read_csv('applicants.csv')
df_applicants = df_applicants.fillna({'income': df_applicants['income'].median()})
df_applicants = pd.get_dummies(df_applicants, columns=['region'], drop_first=False)
df_applicants = df_applicants.copy()
df_applicants[['age', 'income', 'score']] = StandardScaler().fit_transform(df_applicants[['age', 'income', 'score']])
_features = [c for c in df_applicants.select_dtypes(include='number').columns if c != 'approved']
_scorer = f_regression if (pd.api.types.is_numeric_dtype(df_applicants['approved']) and df_applicants['approved'].nunique() > 20) else f_classif
_sel = SelectKBest(_scorer, k=min(2, len(_features))).fit(df_applicants[_features], df_applicants['approved'])
_kept = [c for c, kp in zip(_features, _sel.get_support()) if kp]
df_applicants = df_applicants.drop(columns=[c for c in _features if c not in _kept])
_cols = ['age', 'score']
_pca = PCA(n_components=min(1, len(_cols), len(df_applicants)), random_state=42)
_comp = _pca.fit_transform(df_applicants[_cols])
_names = [f'pc_{i + 1}' for i in range(_comp.shape[1])]
df_applicants = pd.concat([df_applicants.drop(columns=_cols), pd.DataFrame(_comp, columns=_names, index=df_applicants.index)], axis=1)
df_applicants.to_csv('features.csv', index=False)
```

The script needs pandas and scikit-learn. Run it next to `applicants.csv` and
`features.csv` matches the result table at full precision. The **polars** tab
converts to pandas for the scikit-learn steps and writes the same values, with
one difference in the file: polars spells the `region_*` booleans `true` and
`false`, pandas writes `True` and `False`.

## Pitfalls

- **IDs count as numeric features.** Select Features scores every numeric
  column except the target, including `applicant_id`. Here it scored lowest and
  was dropped, which also removes your row identifier. Keep a copy of the ID on
  another branch if you need to join results back.
- **Name the PCA columns.** With **Columns** empty, Reduce Dimensions uses every
  numeric column, including the target `approved`. A component built from the
  target leaks the answer into the features.
- **One-hot columns are not scored.** The `region_*` columns are true/false, not
  numeric, so Select Features neither keeps nor drops them.
- **Fit on training rows only for a real model.** These nodes compute the
  median, means and components from all six rows. For evaluation, split first
  or use in-model preprocessing (below), so test rows do not shape the features.

## Preprocessing inside the model

When the goal is a model you will score new data with, the same steps should run
again, with the same fitted values, at prediction time. Open a train node's
**Advanced options**: the **Preprocessing** section imputes and scales numeric
columns and imputes and one-hot encodes categorical columns inside the
scikit-learn `Pipeline`. The exported script then reapplies them when it scores
new rows.

Use the standalone nodes above to explore and to write engineered tables; use
in-model preprocessing for a model you will deploy.

## Next steps

- [Customer Churn Classification](/examples/ml-classification): train and
  evaluate a classifier
- [ML Nodes Reference](/transformations/machine-learning)
- [Scale Features reference](/transformations/scale-features)
