// Zod schemas for validating each node type's config in the sidebar forms.
import { z } from "zod";

const stringArray = z.array(z.string());

export const filterOperators = [
  "==",
  "!=",
  ">",
  ">=",
  "<",
  "<=",
  "contains",
  "startswith",
  "endswith",
  "isnull",
  "notnull",
] as const;

export const stringOperations = [
  "lower",
  "upper",
  "strip",
  "title",
  "capitalize",
] as const;

export const joinHows = ["inner", "left", "right", "outer"] as const;
export const dtypes = [
  "integer",
  "float",
  "boolean",
  "string",
  "datetime",
] as const;

const inputConfig = z.object({
  dataset_id: z.string().min(1, "Select a dataset"),
});

export const nodeConfigSchemas: Record<string, z.ZodTypeAny> = {
  csvInput: inputConfig,
  excelInput: inputConfig,
  parquetInput: inputConfig,

  dropNulls: z.object({
    subset: stringArray.optional(),
  }),
  fillNulls: z.object({
    value: z.string(),
    columns: stringArray.optional(),
  }),
  dropColumns: z.object({
    columns: stringArray.min(1, "Add at least one column"),
  }),
  renameColumns: z.object({
    mapping: z.record(z.string(), z.string()),
  }),
  selectColumns: z.object({
    columns: stringArray.min(1, "Add at least one column"),
  }),
  removeDuplicates: z.object({
    subset: stringArray.optional(),
    keep: z.enum(["first", "last"]).optional(),
  }),
  filterRows: z.object({
    column: z.string().min(1, "Column is required"),
    operator: z.enum(filterOperators),
    value: z.string().optional(),
  }),
  sortRows: z.object({
    columns: stringArray.min(1, "Add at least one column"),
    ascending: z.boolean().optional(),
  }),
  castDtypes: z.object({
    casts: z.record(z.string(), z.enum(dtypes)),
  }),
  limitRows: z.object({
    n: z.coerce.number().int().min(1, "Must be at least 1"),
  }),
  replaceValues: z.object({
    column: z.string().min(1, "Column is required"),
    to_replace: z.string(),
    value: z.string(),
  }),
  stringTransform: z.object({
    column: z.string().min(1, "Column is required"),
    operation: z.enum(stringOperations),
  }),
  calculatedColumn: z.object({
    column_name: z.string().min(1, "Column name is required"),
    expression: z.string().min(1, "Expression is required"),
  }),
  groupByAggregate: z.object({
    group_by: stringArray.min(1, "Add at least one group-by column"),
    aggregations: z.record(z.string(), z.string()),
  }),
  join: z.object({
    on: z.union([z.string(), stringArray]),
    how: z.enum(joinHows),
  }),
  concatRows: z.object({}),

  csvOutput: z.object({ path: z.string().optional() }),
  excelOutput: z.object({ path: z.string().optional() }),
  parquetOutput: z.object({ path: z.string().optional() }),
};

export function getConfigSchema(type: string): z.ZodTypeAny {
  return nodeConfigSchemas[type] ?? z.object({}).passthrough();
}

export const flowFormSchema = z.object({
  name: z.string().min(1, "Name is required"),
  description: z.string().optional(),
});
export type FlowFormValues = z.infer<typeof flowFormSchema>;
