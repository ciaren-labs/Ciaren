---
title: Customer Churn Classification
description: "Ciaren example: split customer data, train a Random Forest churn classifier, score the held-out test rows and read the metrics with Train / Test Split, Train Classifier, Predict and Evaluate."
search: example machine learning classification churn train test split random forest evaluate predict sklearn mlflow leakage
---

# Customer Churn Classification

You want to predict which customers will leave from their tenure, monthly
charges and support calls, and you want an honest measure of how well the
prediction works. This flow holds back a quarter of the rows, trains a Random
Forest on the rest, scores the held-back rows and computes accuracy, precision,
recall and F1. Every trained model is logged to MLflow, and the flow exports as
a runnable scikit-learn script.

ML nodes are in the **Machine Learning** group of the node palette. See the
[ML Quick Start](/guide/ml-quickstart) for setup.

**You'll use:** File Input → Train / Test Split → Train Classifier → Predict →
Evaluate, with two File Outputs.

<FlowPipeline :nodes='[
  {"type":"input","label":"File Input","detail":"customers.csv"},
  {"type":"ml","label":"Train / Test Split","detail":"test 0.25 · stratify churn · seed 42"},
  {"type":"ml","label":"Train Classifier","detail":"Random Forest on the train output"},
  {"type":"ml","label":"Predict","detail":"test output + model wire"},
  {"type":"ml","label":"Evaluate","detail":"accuracy · precision · recall · f1"},
  {"type":"output","label":"File Output","detail":"metrics.csv"},
  {"type":"output","label":"File Output","detail":"test_predictions.csv, a second branch from Predict"}
]' :vertical="true" />

## Sample data

Save this as `customers.csv`, or [download customers.csv](/samples/ml-classification/customers.csv),
and upload it on the **Datasets** page:

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

`churn` is the target: 1 means the customer left. Half the customers churned.

::: tip Why 16 rows
Training needs at least 10 rows after the test rows are set aside. With fewer,
Train / Test Split stops the run with `the training set would have ~N rows; at
least 10 are required`. Sixteen rows with a test size of 0.25 leave 12 for
training.
:::

## Build the flow

1. **File Input**: **File type** CSV, dataset `customers.csv`.
2. **Train / Test Split**: **Test size** `0.25`, **Stratify by** `churn`,
   **Random seed** `42`. The node has two outputs: the top handle is **train**,
   the bottom handle is **test**.
3. **Train Classifier**: connect the **train** output. Set **Model** to
   *Random Forest*, **Target column** `churn`, **Feature columns**
   `tenure`, `monthly_charges`, `support_calls`, and **Random seed** `42`. The
   node emits a **model** wire.
4. **Predict**: connect the **test** output to its data input and the **model**
   wire to its model input. **Prediction column** stays `prediction`.
5. **Evaluate**: connect Predict. **Task type** *Classification*,
   **True value column** `churn`, **Prediction column** `prediction`.
6. **File Output**: connect Evaluate, **Dataset name** `metrics`.
7. **File Output**: connect Predict as well, **Dataset name**
   `test_predictions`. This lets you read each test prediction next to the true
   value.

Click **Run**. The **Models** page shows the trained model logged in MLflow
with its training-set scores, `train_accuracy` and `train_f1_weighted`. Those
measure the rows the model learned from. The held-out scores from Evaluate are
in `metrics.csv`; Evaluate does not log them to MLflow.

**Advanced options** on the Train Classifier node holds the hyperparameters, the
in-model preprocessing and the MLflow experiment name. Use **Classifier Model**
with **Cross-Validate** when you want fold scores before you train a final
model.

## What the split protects against

A model scored on rows it trained on looks better than it is: it can memorize
them. Train / Test Split puts 4 of the 16 customers aside before training, and
only Predict and Evaluate see them. **Stratify by** `churn` keeps the 50/50
balance in both parts: 6 churned and 6 stayed in training, 2 and 2 in test.

![Sixteen customers split into 12 training rows, 6 churned and 6 stayed, and 4 held-out test rows, 2 of each; the model only learns from the training rows](/illustrations/examples/ml-train-test-split.svg)

The **Random seed** fixes which rows go where, so every run uses the same split
and the metrics are comparable from run to run.

## Why the feature columns are set

If you leave **Feature columns** empty, the model trains on every column except
the target, and that includes `customer_id`. In this sample every odd ID
churned and every even ID stayed. A model could score perfectly by learning
"odd ID means churn", which says nothing about real customers.

![In the sample, customer_id odd always means churn 1 and even means churn 0, so an ID column can predict the target without explaining anything](/illustrations/examples/ml-id-leak.svg)

Listing `tenure`, `monthly_charges` and `support_calls` keeps the ID out.
Predict ignores columns the model did not train on, so `customer_id` still comes
through to the output for reference.

## Result

Predict adds a `prediction` column to the four test rows:

| customer_id | tenure | monthly_charges | support_calls | churn | prediction |
| --- | --- | --- | --- | --- | --- |
| 8 | 41 | 49.9 | 1 | 0 | 0 |
| 3 | 5 | 99.0 | 3 | 1 | 1 |
| 14 | 50 | 44.0 | 0 | 0 | 0 |
| 13 | 6 | 77.5 | 2 | 1 | 1 |

Evaluate turns them into a `metric` / `value` table:

<DataTransform
  transform="Evaluate (task: classification)"
  :before='{
    "columns":["customer_id","churn","prediction"],
    "rows":[[8,0,0],[3,1,1],[14,0,0],[13,1,1]]
  }'
  :after='{
    "columns":["metric","value"],
    "rows":[["accuracy",1.0],["precision",1.0],["recall",1.0],["f1",1.0]]
  }'
/>

These are the values we got with seed 42 (scikit-learn 1.9). The sample is
built to separate cleanly: churners have short tenure, high charges and more
support calls. Read the perfect score as "the flow is wired correctly", not as
model quality. With four test rows, one wrong prediction drops accuracy to 0.75.
Precision, recall and F1 are weighted averages over both classes.

### Check the result

- `test_predictions.csv` has 4 rows, customers 8, 3, 14 and 13: two with
  `churn` 1 and two with 0. None of them appears in the training rows.
- `metrics.csv` has four rows: `accuracy`, `precision`, `recall`, `f1`.
- On the **Models** page, the run lists `train_accuracy` and
  `train_f1_weighted`, scored on the 12 training rows, not the test rows.

## Exported Python

Click **Export** in the editor toolbar and open the **pandas** tab. The
generated script covers the whole flow:

```python
import pandas as pd
import joblib
import mlflow.sklearn
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from sklearn.preprocessing import StandardScaler

df_customers = pd.read_csv('customers.csv')
df_1, df_2 = train_test_split(df_customers, test_size=0.25, random_state=42, stratify=df_customers['churn'])
df_1 = df_1.reset_index(drop=True)
df_2 = df_2.reset_index(drop=True)
_features = ['tenure', 'monthly_charges', 'support_calls']
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
df_4 = df_2.copy()
_model_features = list(getattr(df_3, 'feature_names_in_', df_2.columns))
df_4['prediction'] = df_3.predict(df_2[_model_features])
_metrics = {
    'accuracy': accuracy_score(df_4['churn'], df_4['prediction']),
    'precision': precision_score(df_4['churn'], df_4['prediction'], average='weighted', zero_division=0),
    'recall': recall_score(df_4['churn'], df_4['prediction'], average='weighted', zero_division=0),
    'f1': f1_score(df_4['churn'], df_4['prediction'], average='weighted', zero_division=0),
}
df_5 = pd.DataFrame([{'metric': k, 'value': v} for k, v in _metrics.items()])
df_4.to_csv('test_predictions.csv', index=False)
df_5.to_csv('metrics.csv', index=False)
```

Run it next to `customers.csv` and both output files match the tables above.
The script does not need Ciaren, but its imports need pandas, scikit-learn,
joblib and MLflow installed. The preprocessing (median imputation and standard
scaling) is part of the `Pipeline`, so it is reapplied with the training values
when `predict` runs. Variables follow Ciaren's naming: the input frame is named
after the dataset, node outputs are `df_1`, `df_2`, … and `_`-prefixed names
hold intermediate values.

## Variations

- **Another model:** pick *Logistic Regression*, *Support Vector Machine*,
  *K-Nearest Neighbors* or another option in **Model**; the rest of the flow
  stays the same. *XGBoost* and *LightGBM* need the `ml` extra.
- **Regression:** use **Train Regressor** with a numeric target and set
  Evaluate's **Task type** to *Regression* (RMSE, MAE, R²).
- **Which features matter:** connect a **Feature Importance** node to the
  **model** wire.
- **Retrain regularly:** attach a [schedule](/guide/scheduling).

## Next steps

- [Feature Engineering](/examples/feature-engineering): scale, encode and
  reduce features
- [ML Nodes Reference](/transformations/machine-learning)
- [ML Quick Start](/guide/ml-quickstart)
