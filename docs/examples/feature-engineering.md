---
title: Feature Engineering
description: Prepare features for modeling visually — scale numerics, encode categories, select the best features, and reduce dimensions with PCA.
search: example feature engineering scale encode one-hot select features pca dimensionality reduction sklearn
---

# Feature Engineering

Before training a model, you usually reshape the raw columns into good features.
Ciaren's **Machine Learning** nodes cover the common steps — scaling, encoding,
selection, and dimensionality reduction — and each one previews on real rows so you
can see the effect immediately.

**You'll use:** File Input → Fill Nulls → Encode Categories → Scale Features →
Select Features → Reduce Dimensions (PCA).

<FlowPipeline :nodes='[
  {"type":"input","label":"File Input","detail":"applicants.csv"},
  {"type":"clean","label":"Fill Nulls","detail":"income → median"},
  {"type":"ml","label":"Encode Categories","detail":"onehot: region"},
  {"type":"ml","label":"Scale Features","detail":"standard: age, income"},
  {"type":"ml","label":"Select Features","detail":"kbest by target"},
  {"type":"ml","label":"Reduce Dimensions","detail":"PCA → pc_1, pc_2"}
]' :vertical="true" />

## Sample data

Save this as `applicants.csv` and upload it on the **Datasets** page
(📥 [download applicants.csv](/samples/feature-engineering/applicants.csv)):

```csv
applicant_id,age,income,region,score,approved
1,25,42000,North,0.61,0
2,41,88000,South,0.82,1
3,33,,North,0.55,0
4,52,120000,East,0.91,1
5,29,51000,South,0.64,0
6,46,99000,East,0.88,1
```

## Build the flow

1. **File Input** — File type CSV, select the `applicants.csv` dataset.
2. **Fill Nulls** — `strategy: "median"`, `columns: ["income"]`. (Use the standard
   cleaning [Fill Nulls](/transformations/fill-nulls) node — it works on both
   engines.)
3. **Encode Categories** — `method: "onehot"`, `columns: ["region"]`. Creates dummy
   columns like `region_North`, `region_South`, `region_East`.
4. **Scale Features** — `method: "standard"` (z-score) over `["age", "income"]`.
   Other options are `minmax` and `robust`.
5. **Select Features** — `method: "kbest"` against the `approved` target to keep the
   most relevant columns (or use a `variance` threshold / `correlation` filter).
6. **Reduce Dimensions** — PCA; keep a number of components or a variance fraction.
   The selected columns are replaced by `pc_1`, `pc_2`, ….

Preview after each node to watch the feature space change, then **Run**.

## Scaling, visualized

After Fill Nulls (row 3's missing income becomes the median, 88000):

<DataTransform
  transform="Scale Features (standard)"
  :before='{
    "columns":["age","income"],
    "rows":[[25,42000],[41,88000],[33,88000],[52,120000],[29,51000],[46,99000]]
  }'
  :after='{
    "columns":["age","income"],
    "rows":[[-1.33,-1.46],[0.35,0.25],[-0.49,0.25],[1.51,1.43],[-0.91,-1.12],[0.88,0.66]]
  }'
  :highlight='["age","income"]'
/>

## Engineer features inside the model instead

For modeling, you often want the *same* transformations reapplied automatically at
predict time. Rather than wiring scaling/encoding/imputation as separate nodes,
open a **train node's Advanced → Preprocessing** options — Ciaren bundles numeric
scaling, imputation, and one-hot encoding into the model `Pipeline`, so the exported
scikit-learn script reproduces them exactly when scoring new data.

The standalone nodes above are ideal for **exploration and preview**; the in-model
preprocessing is ideal for **production scoring**.

## Next steps

- [Customer Churn Classification](/examples/ml-classification) — train on these features
- [ML Nodes Reference](/transformations/machine-learning)
- [Fill Nulls](/transformations/fill-nulls)
