# SPDX-License-Identifier: AGPL-3.0-only
"""CSV/Excel dialect handling for dataset ingestion.

Uploads arrive in whatever dialect the user's tooling produced — European
Excel exports use ``;`` as the separator, ``,`` as the decimal mark, and
Latin-1/cp1252 encodings; workbooks carry multiple sheets. Ciaren detects (or
accepts explicitly) these *parse options*, parses once, and then stores a
**normalized** copy (UTF-8, comma-separated, single sheet) as the version's
file — so every later reader (both engines, previews, runs, lazy scans) keeps
using plain default reads and can never drift from what the upload showed.

The options that described the *original* file are persisted on the version
(``parse_options_json``) for transparency in the UI and so exported Python
scripts — which read the user's own original file by name — can emit the
right ``sep=";", encoding="latin-1"`` keywords.
"""

from __future__ import annotations

import csv
import re
from typing import Any

# Whitelists: these values flow into pandas read kwargs and into *generated
# Python source* (codegen emits them via repr), so free-form strings are not
# acceptable — a weird "delimiter" must fail loudly at upload, not at run time.
ALLOWED_DELIMITERS = {",", ";", "\t", "|"}
ALLOWED_ENCODINGS = {
    "utf-8",
    "utf-8-sig",
    "latin-1",
    "cp1252",
    "utf-16",
    "utf-16-le",
    "utf-16-be",
}
ALLOWED_DECIMALS = {".", ","}
_MAX_SHEET_NAME_LEN = 128

# How much of the file the detectors look at. Enough for headers plus a few
# thousand rows; independent of upload size.
_SNIFF_BYTES = 64 * 1024

_DECIMAL_COMMA_CELL = re.compile(r"^-?\d{1,3}(?:\.\d{3})*,\d+$|^-?\d+,\d+$")
_DECIMAL_POINT_CELL = re.compile(r"^-?\d+\.\d+$")


class ParseOptionsError(ValueError):
    """A user-supplied parse option is outside the supported set."""


def validate_parse_options(
    raw: dict[str, Any],
    source_type: str,
) -> dict[str, Any]:
    """Whitelist-validate explicit upload options into a clean options dict.

    Unknown keys are rejected (a typo'd option silently ignored would read as
    "the feature doesn't work"). Options that don't apply to the file type are
    rejected too, for the same reason.
    """
    allowed_keys = {"delimiter", "encoding", "decimal"} if source_type in ("csv", "tsv") else set()
    if source_type == "excel":
        allowed_keys = {"sheet"}
    unknown = set(raw) - allowed_keys
    if unknown:
        applicable = ", ".join(sorted(allowed_keys)) or "none"
        raise ParseOptionsError(
            f"Option(s) {', '.join(sorted(unknown))} do not apply to a "
            f"{source_type.upper()} file (applicable: {applicable})."
        )

    options: dict[str, Any] = {}
    if "delimiter" in raw:
        delim = str(raw["delimiter"])
        if delim == "\\t":  # allow the escaped form a text field naturally sends
            delim = "\t"
        if delim not in ALLOWED_DELIMITERS:
            raise ParseOptionsError("delimiter must be one of: ',' ';' '\\t' '|'")
        options["delimiter"] = delim
    if "encoding" in raw:
        enc = str(raw["encoding"]).lower()
        if enc not in ALLOWED_ENCODINGS:
            raise ParseOptionsError(f"encoding must be one of: {', '.join(sorted(ALLOWED_ENCODINGS))}")
        options["encoding"] = enc
    if "decimal" in raw:
        dec = str(raw["decimal"])
        if dec not in ALLOWED_DECIMALS:
            raise ParseOptionsError("decimal must be '.' or ','")
        options["decimal"] = dec
    if "sheet" in raw:
        sheet = raw["sheet"]
        if isinstance(sheet, str) and sheet.strip().isdigit():
            options["sheet"] = int(sheet.strip())
        elif isinstance(sheet, int):
            options["sheet"] = sheet
        else:
            name = str(sheet).strip()
            if not name or len(name) > _MAX_SHEET_NAME_LEN:
                raise ParseOptionsError("sheet must be a sheet name or a 0-based sheet index")
            options["sheet"] = name
    return options


def detect_encoding(content: bytes) -> str:
    """Best-effort text encoding of ``content``: BOMs first, then strict UTF-8,
    then cp1252 (the Windows superset of Latin-1), with latin-1 as the
    never-fails fallback."""
    if content.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    if content.startswith(b"\xff\xfe"):
        return "utf-16"  # LE BOM — codec 'utf-16' consumes the BOM itself
    if content.startswith(b"\xfe\xff"):
        return "utf-16"
    sample = content[:_SNIFF_BYTES]
    try:
        sample.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        pass
    try:
        sample.decode("cp1252")
        return "cp1252"
    except UnicodeDecodeError:
        return "latin-1"


def detect_delimiter(text_sample: str) -> str:
    """The most plausible CSV delimiter of a decoded sample.

    csv.Sniffer first (restricted to the supported set); if it can't decide,
    fall back to whichever candidate appears most in the first non-empty line
    (a single-column file ends up with ',' — harmless)."""
    try:
        return csv.Sniffer().sniff(text_sample, delimiters=",;\t|").delimiter
    except csv.Error:
        pass
    first_line = next((ln for ln in text_sample.splitlines() if ln.strip()), "")
    counts = {d: first_line.count(d) for d in ALLOWED_DELIMITERS}
    best = max(counts, key=lambda d: counts[d])
    return best if counts[best] > 0 else ","


def detect_decimal(text_sample: str, delimiter: str) -> str:
    """Whether the sample uses decimal commas. Only claimed for ``;``/tab/pipe
    files (a ','-separated file can't distinguish cell commas from separators)
    and only when comma-decimal cells appear while point-decimal cells don't —
    ambiguity resolves to the '.' default."""
    if delimiter == ",":
        return "."
    comma_cells = 0
    point_cells = 0
    for line in text_sample.splitlines()[1:200]:  # skip the header line
        for cell in line.split(delimiter):
            cell = cell.strip().strip('"')
            if _DECIMAL_COMMA_CELL.match(cell):
                comma_cells += 1
            elif _DECIMAL_POINT_CELL.match(cell):
                point_cells += 1
    return "," if comma_cells > 0 and point_cells == 0 else "."


def detect_csv_options(content: bytes, source_type: str) -> dict[str, Any]:
    """Auto-detected parse options for a CSV/TSV upload (encoding always;
    delimiter and decimal only for CSV — TSV is tab-separated by definition)."""
    encoding = detect_encoding(content)
    sample = content[:_SNIFF_BYTES].decode(encoding, errors="replace")
    if source_type == "tsv":
        return {"encoding": encoding, "delimiter": "\t", "decimal": detect_decimal(sample, "\t")}
    delimiter = detect_delimiter(sample)
    return {
        "encoding": encoding,
        "delimiter": delimiter,
        "decimal": detect_decimal(sample, delimiter),
    }


def is_default_dialect(options: dict[str, Any], source_type: str) -> bool:
    """True when the options describe the dialect default readers already use —
    i.e. the stored file needs no normalization and stays byte-identical."""
    if source_type == "csv":
        return bool(
            options.get("delimiter", ",") == ","
            and options.get("encoding", "utf-8") == "utf-8"
            and options.get("decimal", ".") == "."
        )
    if source_type == "tsv":
        return bool(options.get("encoding", "utf-8") == "utf-8" and options.get("decimal", ".") == ".")
    if source_type == "excel":
        return options.get("sheet", 0) in (0, None)
    return True
