# SPDX-License-Identifier: AGPL-3.0-only
"""Security guardrails for ML model loading and hyperparameters.

Two attack surfaces are covered (see docs/ml-architecture.md §6):

1. ``model_uri`` is user-supplied (mlPredict config). It must be an MLflow URI
   (``runs:/`` / ``models:/``, which the MLflow client resolves and validates) or a
   local path that resolves *inside* the artifact root — never an arbitrary path on
   the server (path traversal). Loadable files are restricted to safe formats; a
   pickle is rejected before it can execute code.
2. Hyperparameters are passed to estimator constructors as ``**kwargs``. They must
   be JSON-native values only — never code. We never ``eval``/``exec`` them; a value
   that looks like code is passed through as a literal string sklearn will reject.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

# MLflow URI schemes the client resolves itself (it validates run/model existence).
_ALLOWED_MODEL_URI_SCHEMES = ("runs:/", "models:/")
# On-disk model formats we load. ``.json`` (XGBoost native) is genuinely code-free.
# ``.joblib`` is NOT — joblib serializes with pickle under the hood, so loading a
# crafted ``.joblib`` can execute arbitrary code exactly like a raw ``.pkl``. We
# still allow it because sklearn pipelines need it, but the only thing protecting
# this path is the artifact-root confinement in ``validate_model_uri`` (the file
# must already live under a trusted server directory). Do not treat ``.joblib`` as
# "safe because it isn't a pickle" — it is a pickle. Keep artifact roots trusted.
_ALLOWED_MODEL_SUFFIXES = (".joblib", ".json")
# Refused outright: the bare pickle extensions, so an attacker can't drop a model
# with an obviously-executable suffix. (This does not make ``.joblib`` safe.)
_REJECTED_MODEL_SUFFIXES = (".pkl", ".pickle")


class ModelSecurityError(ValueError):
    """Raised when a model URI or file fails a security check."""


def validate_model_uri(uri: str, artifact_root: str) -> str:
    """Return a safe, canonical model reference or raise :class:`ModelSecurityError`.

    MLflow URIs pass through untouched (the client resolves them). Anything else is
    treated as a local path and must resolve to a location inside ``artifact_root``;
    paths outside it (including ``..`` traversal and absolute paths elsewhere) are
    rejected.
    """
    if not isinstance(uri, str) or not uri.strip():
        raise ModelSecurityError("model_uri must be a non-empty string.")
    for scheme in _ALLOWED_MODEL_URI_SCHEMES:
        if uri.startswith(scheme):
            return uri

    resolved = Path(uri).resolve()
    root = Path(artifact_root).resolve()
    try:
        resolved.relative_to(root)
    except ValueError:
        raise ModelSecurityError(
            f"model_uri {uri!r} is outside the allowed artifact directory. Use a "
            f"'runs:/' or 'models:/' URI, or a path under {root}."
        ) from None
    return str(resolved)


def validate_model_file_suffix(path: str) -> None:
    """Reject model files that aren't a safe, supported format.

    ``.pkl`` / ``.pickle`` are refused with a pointed message because loading a
    pickle executes arbitrary code; any other unknown suffix is also refused.
    """
    suffix = Path(path).suffix.lower()
    if suffix in _REJECTED_MODEL_SUFFIXES:
        raise ModelSecurityError(
            f"Refusing to load {path!r}: pickle files execute arbitrary code on load. "
            f"FlowFrame only loads {', '.join(_ALLOWED_MODEL_SUFFIXES)} artifacts."
        )
    if suffix not in _ALLOWED_MODEL_SUFFIXES:
        raise ModelSecurityError(
            f"Refusing to load {path!r}: unsupported model format {suffix!r}. "
            f"Allowed: {', '.join(_ALLOWED_MODEL_SUFFIXES)}."
        )


# JSON-native scalar types hyperparameters may use.
_JSON_SCALARS = (str, int, float, bool, type(None))


def sanitize_hyperparameters(params: Any) -> dict[str, Any]:
    """Validate that hyperparameters are a flat-ish dict of JSON-native values.

    Returns the dict unchanged when valid; raises :class:`ModelSecurityError`
    otherwise. Values are never evaluated — this only rejects non-serializable
    inputs (e.g. callables) that could not have come from a JSON graph config and
    would indicate tampering.
    """
    if params is None:
        return {}
    if not isinstance(params, dict):
        raise ModelSecurityError("hyperparameters must be an object (mapping of name -> value).")
    for key, value in params.items():
        if not isinstance(key, str):
            raise ModelSecurityError(f"hyperparameter names must be strings; got {key!r}.")
        _check_json_native(key, value)
    return params


def _check_json_native(key: str, value: Any) -> None:
    if isinstance(value, bool) or isinstance(value, _JSON_SCALARS):
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            _check_json_native(key, item)
        return
    if isinstance(value, dict):
        for k, v in value.items():
            if not isinstance(k, str):
                raise ModelSecurityError(f"hyperparameter {key!r}: nested keys must be strings.")
            _check_json_native(key, v)
        return
    raise ModelSecurityError(
        f"hyperparameter {key!r} has a non-JSON value of type {type(value).__name__}; "
        f"only numbers, strings, booleans, null, lists, and objects are allowed."
    )
