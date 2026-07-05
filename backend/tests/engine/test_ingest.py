# SPDX-License-Identifier: AGPL-3.0-only
"""Dialect detection and validation for dataset ingestion (app/engine/ingest.py)."""

import pytest

from app.engine.ingest import (
    ParseOptionsError,
    detect_csv_options,
    detect_decimal,
    detect_delimiter,
    detect_encoding,
    is_default_dialect,
    validate_parse_options,
)

# -- encoding -----------------------------------------------------------------


def test_detect_encoding_utf8_plain() -> None:
    assert detect_encoding("a,b\n1,café\n".encode()) == "utf-8"


def test_detect_encoding_utf8_bom() -> None:
    assert detect_encoding(b"\xef\xbb\xbfa,b\n1,2\n") == "utf-8-sig"


def test_detect_encoding_latin1_bytes() -> None:
    # é in Latin-1 is 0xE9 — invalid as UTF-8, valid as cp1252.
    assert detect_encoding("a;b\n1;café\n".encode("latin-1")) == "cp1252"


def test_detect_encoding_utf16_bom() -> None:
    assert detect_encoding("a,b\n1,2\n".encode("utf-16")) == "utf-16"


def test_detect_encoding_cp1252_specific() -> None:
    # 0x80 is € in cp1252 but undefined in latin-1's C1 range only via cp1252.
    assert detect_encoding(b"a;b\n1;pr\x80cio\n") == "cp1252"


# -- delimiter ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("sample", "expected"),
    [
        ("a;b;c\n1;2;3\n", ";"),
        ("a\tb\tc\n1\t2\t3\n", "\t"),
        ("a|b|c\n1|2|3\n", "|"),
        ("a,b,c\n1,2,3\n", ","),
    ],
)
def test_detect_delimiter(sample: str, expected: str) -> None:
    assert detect_delimiter(sample) == expected


def test_detect_delimiter_single_column_falls_back_to_comma() -> None:
    assert detect_delimiter("justonecolumn\nvalue\n") == ","


# -- decimal --------------------------------------------------------------------


def test_detect_decimal_comma_in_semicolon_file() -> None:
    assert detect_decimal("a;b\nx;1,5\ny;2,75\n", ";") == ","


def test_detect_decimal_with_thousands_separators() -> None:
    assert detect_decimal("a;b\nx;1.234,56\n", ";") == ","


def test_detect_decimal_ambiguous_resolves_to_point() -> None:
    # Both styles present: don't guess.
    assert detect_decimal("a;b;c\nx;1,5;2.5\n", ";") == "."


def test_detect_decimal_never_claimed_for_comma_files() -> None:
    assert detect_decimal('a,b\nx,"1,5"\n', ",") == "."


def test_detect_decimal_integer_only_stays_point() -> None:
    assert detect_decimal("a;b\nx;15\ny;27\n", ";") == "."


# -- full detection -------------------------------------------------------------


def test_detect_csv_options_european_export() -> None:
    content = "producto;precio\ncafé;1,50\ntécnica;2,75\n".encode("latin-1")
    assert detect_csv_options(content, "csv") == {
        "encoding": "cp1252",
        "delimiter": ";",
        "decimal": ",",
    }


def test_detect_csv_options_tsv_keeps_tab() -> None:
    opts = detect_csv_options(b"a\tb\n1\t2\n", "tsv")
    assert opts["delimiter"] == "\t"
    assert opts["encoding"] == "utf-8"


# -- validation -------------------------------------------------------------------


def test_validate_accepts_escaped_tab() -> None:
    assert validate_parse_options({"delimiter": "\\t"}, "csv") == {"delimiter": "\t"}


def test_validate_rejects_unknown_delimiter() -> None:
    with pytest.raises(ParseOptionsError, match="delimiter"):
        validate_parse_options({"delimiter": "##"}, "csv")


def test_validate_rejects_unknown_encoding() -> None:
    with pytest.raises(ParseOptionsError, match="encoding"):
        validate_parse_options({"encoding": "ebcdic"}, "csv")


def test_validate_rejects_inapplicable_option() -> None:
    with pytest.raises(ParseOptionsError, match="sheet"):
        validate_parse_options({"sheet": "Data"}, "csv")
    with pytest.raises(ParseOptionsError, match="delimiter"):
        validate_parse_options({"delimiter": ";"}, "excel")
    with pytest.raises(ParseOptionsError, match="delimiter"):
        validate_parse_options({"delimiter": ";"}, "parquet")


def test_validate_sheet_index_and_name() -> None:
    assert validate_parse_options({"sheet": "2"}, "excel") == {"sheet": 2}
    assert validate_parse_options({"sheet": "Ventas"}, "excel") == {"sheet": "Ventas"}


def test_is_default_dialect() -> None:
    assert is_default_dialect({"delimiter": ",", "encoding": "utf-8", "decimal": "."}, "csv")
    assert not is_default_dialect({"delimiter": ";", "encoding": "utf-8", "decimal": "."}, "csv")
    assert not is_default_dialect({"delimiter": ",", "encoding": "cp1252", "decimal": "."}, "csv")
    assert not is_default_dialect({"delimiter": ",", "encoding": "utf-8", "decimal": ","}, "csv")
    assert is_default_dialect({}, "parquet")
    assert is_default_dialect({"sheet": 0}, "excel")
    assert not is_default_dialect({"sheet": "Ventas"}, "excel")
