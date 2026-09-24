import { useEffect, useRef } from "react";
import { Select } from "@/components/ui/select";
import { useObjectDialect } from "@/features/connections/hooks";
import {
  DECIMAL_OPTIONS,
  DELIMITER_OPTIONS,
  DIALECT_KEYS,
  ENCODING_OPTIONS,
  describeDialect,
} from "@/lib/csvDialect";
import { Field } from "../configFields";
import type { NodeConfigRenderProps } from "./shared";

/** Dialect overrides for a storage CSV/TSV input, pre-filled once per picked
 *  file from the server-side detection. "Auto-detect" (unset) makes each read
 *  detect again; a set value always wins over detection. */
export function StorageDialectFields({ c, errors, set }: Omit<NodeConfigRenderProps, "columns">) {
  const format = c.format === "tsv" ? "tsv" : "csv";
  const path = (c.path as string) || null;
  const detection = useObjectDialect((c.connection_id as string) || null, path, format);
  const detected = detection.data;

  // Pre-fill only the first time a file's detection arrives, and never over
  // values already set — so choosing "Auto-detect" afterwards sticks.
  const prefilledFor = useRef<string | null>(null);
  const fileKey = `${c.connection_id}|${path}|${format}`;
  useEffect(() => {
    if (!detected || prefilledFor.current === fileKey) return;
    prefilledFor.current = fileKey;
    if (DIALECT_KEYS.some((k) => c[k])) return;
    const patch: Record<string, string> = {};
    for (const k of DIALECT_KEYS) {
      const v = detected[k];
      if (v && !(k === "delimiter" && format === "tsv")) patch[k] = v;
    }
    if (Object.keys(patch).length) set(patch);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- runs per detection result, not per config edit
  }, [detected, fileKey]);

  const summary = detected ? describeDialect(detected) : null;
  let status: React.ReactNode = null;
  if (detection.isFetching) {
    status = <p className="text-[11px] text-muted-foreground">Detecting delimiter and encoding…</p>;
  } else if (detection.isError) {
    status = (
      <p className="text-[11px] text-amber-600">
        Couldn't detect the dialect — reads use comma / UTF-8 unless you set them below.
      </p>
    );
  } else if (detected) {
    status = (
      <p className="text-[11px] text-muted-foreground">
        {summary
          ? `Detected: ${summary}`
          : "No dialect detected — reads use comma / UTF-8 unless you set them below."}
      </p>
    );
  }

  const choose = (key: (typeof DIALECT_KEYS)[number]) => (e: React.ChangeEvent<HTMLSelectElement>) =>
    set({ [key]: e.target.value || undefined });

  return (
    <>
      {status}
      {format === "csv" && (
        <Field label="Separator" error={errors.delimiter} help="Overrides the detected column separator.">
          <Select aria-label="Separator" value={c.delimiter ?? ""} onChange={choose("delimiter")}>
            <option value="">Auto-detect</option>
            {DELIMITER_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </Select>
        </Field>
      )}
      <Field label="Encoding" error={errors.encoding} help="Overrides the detected text encoding.">
        <Select aria-label="Encoding" value={c.encoding ?? ""} onChange={choose("encoding")}>
          <option value="">Auto-detect</option>
          {ENCODING_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </Select>
      </Field>
      <Field label="Decimal mark" error={errors.decimal} help="Overrides the detected decimal separator.">
        <Select aria-label="Decimal mark" value={c.decimal ?? ""} onChange={choose("decimal")}>
          <option value="">Auto-detect</option>
          {DECIMAL_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </Select>
      </Field>
    </>
  );
}
