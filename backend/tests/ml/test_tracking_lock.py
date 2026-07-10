# SPDX-License-Identifier: AGPL-3.0-only
"""mlflow.set_tracking_uri (configure_mlflow) mutates the MLflow SDK's
process-global state. THREAD execution mode runs multiple flows concurrently
in one process, so two trainings racing configure_mlflow()-through-log_model()
could log one run's params/model against the OTHER run's tracking store.
mlflow_tracking_lock() serializes that whole critical section; these tests
prove the lock itself provides real mutual exclusion, not the (slow, heavy)
real MLflow calls it protects."""

import threading
import time

import numpy as np
import pandas as pd

import app.ml.tracking as tracking_module
from app.engine.backends import get_engine
from app.engine.transformations.ml.train import TrainClassifierTransformation
from app.ml.tracking import mlflow_tracking_lock
from app.plugins.model_store import MlflowModelStore


def test_mlflow_tracking_lock_is_a_singleton():
    # A fresh Lock() per call would serialize nothing — every caller must
    # contend on the exact same lock object.
    assert mlflow_tracking_lock() is mlflow_tracking_lock()


def test_mlflow_tracking_lock_serializes_concurrent_critical_sections():
    """Simulates the real race: each worker "configures" a shared resource to
    its own id inside the lock, holds it briefly (standing in for the
    mlflow.start_run()/log_model() calls), then checks nothing else changed
    it — exactly the failure mode a missing lock would allow."""
    shared_state = {"owner": None}
    violations: list[tuple[int, object]] = []

    def worker(worker_id: int) -> None:
        with mlflow_tracking_lock():
            shared_state["owner"] = worker_id
            time.sleep(0.005)  # widen the window a missing lock would expose
            if shared_state["owner"] != worker_id:
                violations.append((worker_id, shared_state["owner"]))

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(12)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert violations == []


def test_mlflow_tracking_lock_blocks_a_second_acquirer_until_released():
    lock = mlflow_tracking_lock()
    acquired_second = threading.Event()

    with lock:

        def try_acquire() -> None:
            with lock:
                acquired_second.set()

        t = threading.Thread(target=try_acquire)
        t.start()
        # The second thread must NOT acquire while we still hold the lock.
        assert not acquired_second.wait(timeout=0.05)

    # Released now — the waiting thread should get in promptly.
    t.join(timeout=1)
    assert acquired_second.is_set()


class _SpyLock:
    """Delegates to the real lock while counting how many times it was
    acquired — proves a call site actually engages the lock, not just that
    the lock mechanism itself works in isolation."""

    def __init__(self, real: threading.Lock) -> None:
        self._real = real
        self.acquire_count = 0

    def __enter__(self) -> None:
        self.acquire_count += 1
        self._real.acquire()

    def __exit__(self, *exc: object) -> None:
        self._real.release()


def _classification_frame(n: int = 60) -> pd.DataFrame:
    rng = np.random.RandomState(0)
    x1, x2 = rng.normal(size=n), rng.normal(size=n)
    return pd.DataFrame({"x1": x1, "x2": x2, "target": (x1 + x2 > 0).astype(int)})


def test_core_mltrain_logging_actually_acquires_the_lock(ml_env, monkeypatch):
    spy = _SpyLock(threading.Lock())
    monkeypatch.setattr(tracking_module, "mlflow_tracking_lock", lambda: spy)

    engine = get_engine("pandas")
    frame = engine.from_pandas(_classification_frame())
    TrainClassifierTransformation().execute_with_metadata(
        engine, {"in": frame}, {"model_type": "random_forest_classifier", "target_column": "target", "seed": 1}
    )

    assert spy.acquire_count == 1


def test_plugin_model_store_logging_actually_acquires_the_lock(ml_env, monkeypatch):
    spy = _SpyLock(threading.Lock())
    monkeypatch.setattr(tracking_module, "mlflow_tracking_lock", lambda: spy)

    from sklearn.linear_model import LogisticRegression

    df = _classification_frame()
    model = LogisticRegression().fit(df[["x1", "x2"]], df["target"])
    store = MlflowModelStore(plugin_id="test-plugin", granted_permissions=frozenset())
    store.log_sklearn_model(
        model,
        model_type="logistic_regression",
        task_type="classification",
        target_column="target",
        feature_columns=("x1", "x2"),
    )

    assert spy.acquire_count == 1


def test_model_loading_actually_acquires_the_lock(ml_env, monkeypatch):
    """Residual-gap regression: configure_mlflow() call sites that only ever
    read (no start_run()/log_model() afterward) still mutate the same
    process-global state a concurrent training run's locked section depends
    on, so they need the lock too — not just the write-heavy call sites."""
    from app.ml.loader import load_model

    # Train and log a real model first (unlocked spy — this call's own
    # acquisition isn't what's under test here).
    engine = get_engine("pandas")
    frame = engine.from_pandas(_classification_frame())
    _out, meta = TrainClassifierTransformation().execute_with_metadata(
        engine, {"in": frame}, {"model_type": "random_forest_classifier", "target_column": "target", "seed": 2}
    )
    assert meta is not None and meta.model_uri

    spy = _SpyLock(threading.Lock())
    monkeypatch.setattr(tracking_module, "mlflow_tracking_lock", lambda: spy)
    load_model(meta.model_uri)

    assert spy.acquire_count == 1


def test_production_dependency_check_actually_acquires_the_lock(ml_env, monkeypatch):
    from app.ml.registry_deps import production_models_for_dataset

    spy = _SpyLock(threading.Lock())
    monkeypatch.setattr(tracking_module, "mlflow_tracking_lock", lambda: spy)

    result = production_models_for_dataset("some-dataset-id")

    assert spy.acquire_count == 1
    assert result == []  # no registered models exist in this test's mlruns dir


def test_connection_test_actually_acquires_the_lock(ml_env, monkeypatch, tmp_path):
    # Aliased on import: pytest would otherwise try to collect this as a test
    # function (it starts with "test_") and fail on its required argument.
    from app.ml.tracking import test_tracking_uri as check_tracking_uri

    spy = _SpyLock(threading.Lock())
    monkeypatch.setattr(tracking_module, "mlflow_tracking_lock", lambda: spy)

    check_tracking_uri(str(tmp_path / "other_mlruns"))

    assert spy.acquire_count == 1
