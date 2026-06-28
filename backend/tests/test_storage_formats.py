"""All five file formats round-trip through the storage serializer and the local
storage connector (the connection auto-created at startup)."""

from __future__ import annotations

import pandas as pd
import pytest

from app.connectors.storage_base import (
    FILE_FORMATS,
    StorageSpec,
    deserialize_dataframe,
    serialize_dataframe,
)

_DF = pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})


@pytest.mark.parametrize("fmt", FILE_FORMATS)
def test_serializer_roundtrip(fmt):
    data, content_type = serialize_dataframe(_DF, fmt)
    assert isinstance(data, bytes) and data
    assert content_type
    back = deserialize_dataframe(data, fmt)
    # csv/excel/parquet/json preserve the column names; text collapses to one column.
    if fmt == "text":
        assert len(back) == len(_DF)
    else:
        assert list(back.columns) == ["a", "b"]
        assert len(back) == 3


def test_serializer_rejects_unknown_format():
    from app.connectors.base import ConnectorError

    with pytest.raises(ConnectorError, match="Unsupported format"):
        serialize_dataframe(_DF, "yaml")
    with pytest.raises(ConnectorError, match="Unsupported format"):
        deserialize_dataframe(b"{}", "yaml")


@pytest.mark.parametrize("fmt", FILE_FORMATS)
def test_local_connector_writes_and_reads_every_format(tmp_path, fmt):
    from app.connectors.local_storage import LocalStorageConnector

    conn = LocalStorageConnector()
    spec = StorageSpec(provider="local", bucket=str(tmp_path))
    ext = {"csv": "csv", "excel": "xlsx", "parquet": "parquet", "json": "json", "text": "txt"}[fmt]
    path = f"out.{ext}"

    conn.write_file(spec, _DF, path, fmt, "overwrite")
    assert (tmp_path / path).exists()
    back = conn.read_file(spec, path, fmt)
    assert len(back) == len(_DF)
