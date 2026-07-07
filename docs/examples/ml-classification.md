---
title: Customer Churn Classification
description: Train, evaluate, and score a customer-churn classifier visually — split, train, predict, evaluate — and export the scikit-learn code.
search: example machine learning classification churn train test split random forest evaluate predict sklearn mlflow
---

# Customer Churn Classification

Build a complete supervised-learning workflow on the canvas: split the data, train
a classifier, score the held-out test set, and read the metrics — then export a
runnable scikit-learn script. Every model is logged to MLflow automatically.

ML nodes appear under **Machine Learning** in the palette by default — see the
[ML Quick Start](/guide/ml-quickstart) for setup details.

**You'll use:** File Input → Train / Test Split → Train Classifier → Predict →
Evaluate → File Output.

<FlowPipeline :nodes='[
  {"type":"input","label":"File Input","detail":"customers.csv"},
  {"type":"ml","label":"Train / Test Split","detail":"test 25% · stratify churn · seed 42"},
  {"type":"ml","label":"Train Classifier","detail":"Random Forest → model wire"},
  {"type":"ml","label":"Predict","detail":"score the test set"},
  {"type":"ml","label":"Evaluate","detail":"accuracy · precision · recall · f1"},
  {"type":"output","label":"File Output","detail":"metrics.csv"}
]' :vertical="true" />

## Sample data

Save this as `customers.csv` and upload it on the **Datasets** page
(📥 [download customers.csv](/samples/ml-classification/customers.csv)):

```csv
customer_id,tenure,monthly_charges,support_calls,churn
1,2,79.9,4,1
2,34,55.1,0,0
3,5,99.0,3,1
4,48,42.3,1,0
5,9,88.5,5,1
6,60,38.0,0,0
7,3,72.4,2,1
8,41,49.9,1,0
9,4,85.0,3,1
10,55,40.5,0,0
11,7,91.2,4,1
12,38,47.8,1,0
13,6,77.5,2,1
14,50,44.0,0,0
15,2,95.0,5,1
16,45,39.9,0,0
```

::: tip Why 16 rows
Training needs at least 10 rows once the test split is set aside — a smaller
sample fails with `need at least 10 rows to train`. 16 rows leaves a
comfortable margin above that floor with `test_size: 0.25`.
:::

The target column is `churn` (1 = the customer left). The remaining columns are
features.

## Build the flow

1. **File Input** — File type CSV, select the `customers.csv` dataset.
2. **Train / Test Split** — `test_size: 0.25`, `stratify_column: "churn"`,
   `seed: 42`. This node has **two outputs**: `train` and `test`.
3. **Train Classifier** — wire the **`train`** output here. Pick **Random Forest**,
   set `target_column: "churn"`, leave features empty (uses all columns except the
   target), set the required `seed: 42`. The node emits a purple **`model`** wire.
   - *Optional:* open **Advanced options** for the full hyperparameter set,
     in-pipeline preprocessing, and the MLflow experiment name. Use **Classifier
     Model** plus **Cross-Validate** if you want fold scores without training a
     final model first.
4. **Predict** — wire the **`test`** split as the data input and the **`model`**
   wire from the train node. It adds a `prediction` column.
5. **Evaluate** — `task_type: classification`, `target_column: "churn"`,
   `prediction_column: "prediction"`. It returns a tidy `metric` / `value` table.
6. **File Output** — write the metrics table as `metrics.csv`.

Use the **live preview** at each step, then **Run** the flow. Open the **Models**
page to see the run logged in MLflow with its metrics and lineage.

## What Evaluate produces

With `test_size: 0.25` on 16 rows, the held-out test set is 4 rows. This
toy dataset separates cleanly on tenure/charges/support calls alone, so the
model gets all four right:

<DataTransform
  transform="Evaluate (task=classification)"
  :before='{
    "columns":["customer_id","churn","prediction"],
    "rows":[[8,0,0],[3,1,1],[14,0,0],[13,1,1]]
  }'
  :after='{
    "columns":["metric","value"],
    "rows":[["accuracy",1.0],["precision",1.0],["recall",1.0],["f1",1.0]]
  }'
/>

## Exported Python

Click **Export → Python**. The split and training steps generate a faithful
scikit-learn script (this is the real codegen pattern — preprocessing is bundled
into the `Pipeline` so it's reapplied identically at predict time):

```python
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

df_customers = pd.read_csv('customers.csv')
df_1, df_2 = train_test_split(df_customers, test_size=0.25, random_state=42, stratify=df_customers['churn'])
df_1 = df_1.reset_index(drop=True)
df_2 = df_2.reset_index(drop=True)

_features = [c for c in df_1.columns if c != 'churn']
_X = df_1[_features]
_numeric = [c for c in _features if pd.api.types.is_numeric_dtype(_X[c])]
_categorical = [c for c in _features if c not in _numeric]
_transformers = []
if _numeric:
    _transformers.append(('num', Pipeline([('impute', SimpleImputer(strategy='median')), ('scale', StandardScaler())]), _numeric))
if _categorical:
    _transformers.append(('cat', Pipeline([('impute', SimpleImputer(strategy='most_frequent')), ('encode', OneHotEncoder(handle_unknown='ignore'))]), _categorical))
_preprocessor = ColumnTransformer(_transformers, remainder='drop')
_y = df_1['churn']
df_3 = Pipeline([('preprocessor', _preprocessor), ('model', RandomForestClassifier(random_state=42))])
df_3.fit(_X, _y)
```

Variables follow Ciaren's generated naming (the input frame is named after your
dataset, node outputs get `df_1`, `df_2`, …, and `_`-prefixed locals hold
intermediates) rather than hand-picked names — export the flow yourself to see
it verbatim. The Predict and Evaluate nodes continue the script — scoring
`df_2` (the test split) and computing the metric table — so the whole flow runs
anywhere scikit-learn is installed, with no Ciaren dependency.

## Variations

- **Different model?** Swap Random Forest for Logistic Regression, XGBoost,
  LightGBM, SVM, or KNN in the Train Classifier node — the rest of the flow is
  unchanged.
- **Regression instead?** Use **Train Regressor** with a numeric target and an
  Evaluate node set to `task_type: regression` (RMSE, MAE, R²).
- **Which features matter?** Add a **Feature Importance** node off the `model`
  wire (tree-based and linear models).
- **Retrain on a schedule?** Attach a [schedule](/guide/scheduling) to retrain
  periodically as new data arrives.

## Next steps

- [Feature Engineering](/examples/feature-engineering) — scale, encode, and reduce features
- [ML Nodes Reference](/transformations/machine-learning)
- [ML Quick Start](/guide/ml-quickstart)
