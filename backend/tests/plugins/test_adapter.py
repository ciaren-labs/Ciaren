"""Unit tests for the plugin -> BaseTransformation adapter."""

from __future__ import annotations

import pandas as pd
import pytest

from app.engine.backends.base import get_engine
from app.plugin_api import NodeRuntime, NodeSpec, PortSpec
from app.plugins.adapter import PluginNodeExportError, PluginTransformation


class _AddColumnRuntime(NodeRuntime):
    def execute(self, inputs, config):
        df = inputs["in"].copy()
        df[config.get("col", "x")] = config.get("val", 1)
        return {"out": df}

    def to_python_code(self, input_vars, output_vars, config):
        return f"{output_vars['out']} = {input_vars['in']}.assign({config.get('col', 'x')}={config.get('val', 1)!r})"


class _NoCodeRuntime(NodeRuntime):
    def execute(self, inputs, config):
        return {"out": inputs["in"]}


def _spec(**kw):
    kw.setdefault("inputs", (PortSpec(id="in"),))
    kw.setdefault("outputs", (PortSpec(id="out"),))
    return NodeSpec(id="t.node", label="T", category="columns", **kw)


def test_handles_derived_from_spec():
    spec = _spec(
        inputs=(
            PortSpec(id="in"),
            PortSpec(id="model", type="model", required=False),
        )
    )
    tf = PluginTransformation(spec, _AddColumnRuntime())
    assert tf.input_handles == ("in",)
    assert tf.optional_input_handles == ("model",)
    assert tf.multi_input is False
    assert tf.emits_pandas_code is True


def test_multi_input_flag():
    spec = _spec(inputs=(PortSpec(id="in", multi=True),))
    assert PluginTransformation(spec, _AddColumnRuntime()).multi_input is True


@pytest.mark.parametrize("engine_name", ["pandas", "polars"])
def test_execute_bridges_engine_frames(engine_name):
    engine = get_engine(engine_name)
    tf = PluginTransformation(_spec(), _AddColumnRuntime())
    frame = engine.from_pandas(pd.DataFrame({"a": [1, 2, 3]}))
    out = tf.execute(engine, {"in": frame}, {"col": "greeting", "val": "hi"})
    result = engine.to_pandas(out["out"])
    assert list(result["greeting"]) == ["hi", "hi", "hi"]
    assert list(result["a"]) == [1, 2, 3]


def test_validate_config_delegates():
    class _Strict(NodeRuntime):
        def execute(self, inputs, config):
            return {"out": inputs["in"]}

        def validate_config(self, config):
            if not config.get("ok"):
                raise ValueError("need ok")

    tf = PluginTransformation(_spec(), _Strict())
    with pytest.raises(ValueError, match="need ok"):
        tf.validate_config({})
    tf.validate_config({"ok": True})  # no raise


def test_to_python_and_polars_code():
    tf = PluginTransformation(_spec(), _AddColumnRuntime())
    py = tf.to_python_code({"in": "df_1"}, {"out": "df_2"}, {"col": "g", "val": 5})
    assert py == "df_2 = df_1.assign(g=5)"
    # polars export reuses the pandas code (bridged by emits_pandas_code).
    assert tf.to_polars_code({"in": "df_1"}, {"out": "df_2"}, {"col": "g", "val": 5}) == py


def test_export_error_when_runtime_has_no_code():
    tf = PluginTransformation(_spec(), _NoCodeRuntime())
    with pytest.raises(PluginNodeExportError):
        tf.to_python_code({"in": "df_1"}, {"out": "df_2"}, {})
