"""FlowFrame ML extension.

Kept import-light: nothing here imports scikit-learn, xgboost, lightgbm, or
mlflow at module load. Availability is detected lazily so the base install stays
lean and ETL-only environments never pay for ML imports. See docs/ml-architecture.md.
"""
