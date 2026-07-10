// Small pieces shared across NodeConfigForm and its per-family config modules
// (components/flow/config/*). Kept separate from NodeConfigForm.tsx itself so
// family modules never need to import back from it (that would be circular).

export type ErrorMap = Record<string, string>;

// Operators that compare against a value vs. those that don't need one.
export const VALUELESS_OPERATORS = new Set(["isnull", "notnull"]);

/** Values every family renderer needs: the raw config (loosely typed for the
 *  same reason the original inline switch was — per-node shapes vary), the
 *  validation errors keyed by field, a patch-and-emit setter, and the columns
 *  available on the incoming wire. */
export interface NodeConfigRenderProps {
  c: Record<string, any>;
  errors: ErrorMap;
  set: (patch: Record<string, unknown>) => void;
  columns: string[];
}
