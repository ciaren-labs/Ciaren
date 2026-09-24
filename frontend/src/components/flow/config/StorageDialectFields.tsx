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

/** Dialect overrides for a storage CSV/TSV input. The server-side detection is
 *  shown as information only: opening the node never writes config, so an
 *  unset field ("Auto-detect") keeps detecting on every preview and run. The
 *  detected values are written only when the user clicks "Use detected values"
 *  (or picks them in a field); a set value always wins over detection. */
export function StorageDialectFields({ c, errors, set }: Omit<NodeConfigRenderProps, "columns">) {
  const format = c.format === "tsv" ? "tsv" : "csv";
  const path = (c.path as string) || null;
  const detection = useObjectDialect((c.connection_id as string) || null, path, format);
  const detected = detection.data;

  // The detected values that apply to this format (TSV is always tab-separated).
  const detectedPatch: Record<string, string> = {};
  for (const k of DIALECT_KEYS) {
    const v = detected?.[k];
    if (v && !(k === "delimiter" && format === "tsv")) detectedPatch[k] = v;
  }
  const canUseDetected = DIALECT_KEYS.some((k) => detectedPatch[k] && detectedPatch[k] !== c[k]);
  const autoLabel = (value: string | undefined, options: readonly { value: string; label: string }[]) => {
    const label = value ? (options.find((o) => o.value === value)?.label ?? value) : null;
    return label ? `Auto-detect (${label})` : "Auto-detect";
  };

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
      <p className="flex flex-wrap items-center gap-1 text-[11px] text-muted-foreground">
        {summary
          ? `Detected: ${summary}`
          : "No dialect detected — reads use comma / UTF-8 unless you set them below."}
        {canUseDetected && (
          <button
            type="button"
            className="font-medium text-primary underline underline-offset-2"
            onClick={() => set(detectedPatch)}
          >
            Use detected values
          </button>
        )}
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
            <option value="">{autoLabel(detectedPatch.delimiter, DELIMITER_OPTIONS)}</option>
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
          <option value="">{autoLabel(detectedPatch.encoding, ENCODING_OPTIONS)}</option>
          {ENCODING_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </Select>
      </Field>
      <Field label="Decimal mark" error={errors.decimal} help="Overrides the detected decimal separator.">
        <Select aria-label="Decimal mark" value={c.decimal ?? ""} onChange={choose("decimal")}>
          <option value="">{autoLabel(detectedPatch.decimal, DECIMAL_OPTIONS)}</option>
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
