# SPDX-License-Identifier: AGPL-3.0-only
"""Machine-learning transformation nodes (scikit-learn / XGBoost / LightGBM).

Import-light by contract: modules in this package must not import sklearn,
xgboost, lightgbm, or mlflow at module top level — only inside method bodies —
so registering the nodes stays cheap and the heavy libraries load only when a
node actually runs. The registry pulls these in only when the core ML libraries
are available (see app/engine/registry.py + app/ml/availability.py).
"""
