/** CSV/TSV dialect choices shared by dataset uploads and the storage input node.
 *  Values mirror the backend whitelist (app/engine/ingest.py) — anything else
 *  is rejected server-side. */

export const DELIMITER_OPTIONS = [
  { value: ",", label: "Comma (,)" },
  { value: ";", label: "Semicolon (;)" },
  { value: "\t", label: "Tab" },
  { value: "|", label: "Pipe (|)" },
] as const;

export const ENCODING_OPTIONS = [
  { value: "utf-8", label: "UTF-8" },
  { value: "utf-8-sig", label: "UTF-8 (BOM)" },
  { value: "latin-1", label: "Latin-1" },
  { value: "cp1252", label: "Windows-1252" },
  { value: "utf-16", label: "UTF-16" },
  { value: "utf-16-le", label: "UTF-16 LE" },
  { value: "utf-16-be", label: "UTF-16 BE" },
] as const;

export const DECIMAL_OPTIONS = [
  { value: ".", label: "Point (.)" },
  { value: ",", label: "Comma (,)" },
] as const;

type OptionValues<T extends readonly { value: string }[]> = [T[number]["value"], ...T[number]["value"][]];
const values = <T extends readonly { value: string }[]>(opts: T) => opts.map((o) => o.value) as OptionValues<T>;
export const DELIMITER_VALUES = values(DELIMITER_OPTIONS);
export const ENCODING_VALUES = values(ENCODING_OPTIONS);
export const DECIMAL_VALUES = values(DECIMAL_OPTIONS);

/** Node-config keys that override a delimited file's detected dialect. */
export const DIALECT_KEYS = ["delimiter", "encoding", "decimal"] as const;
/** Config patch dropping every dialect override (the file or format changed). */
export const CLEAR_DIALECT = { delimiter: undefined, encoding: undefined, decimal: undefined };

export interface CsvDialect {
  delimiter?: string | null;
  encoding?: string | null;
  decimal?: string | null;
}

/** Human-readable summary of the detected values only (null when nothing was
 *  detected), e.g. "Semicolon (;) · cp1252 · decimal comma". */
export function describeDialect(d: CsvDialect): string | null {
  const parts = [
    d.delimiter ? (DELIMITER_OPTIONS.find((o) => o.value === d.delimiter)?.label ?? d.delimiter) : null,
    d.encoding ?? null,
    d.decimal === "," ? "decimal comma" : null,
  ].filter(Boolean);
  return parts.length ? parts.join(" · ") : null;
}
