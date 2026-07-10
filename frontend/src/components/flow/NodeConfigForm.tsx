import { useEffect, useState } from "react";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { cn } from "@/lib/utils";
import { Dataset } from "@/features/datasets/types";
import { getConfigSchema } from "@/lib/validators";
import { Field } from "./configFields";
import { useConnections, useConnectionObjects, useConnectionTables } from "@/features/connections/hooks";
import { getNodeTypeDef } from "@/lib/nodeCatalog";
import { SchemaConfigFields, fieldsFromDefaults } from "./SchemaConfigFields";
import { renderChartConfig } from "./config/charts";
import { renderCleaningConfig } from "./config/cleaning";
import { renderMlConfig } from "./config/ml";
import { renderQualityConfig } from "./config/quality";
import { renderReshapeConfig } from "./config/reshape";
import type { ErrorMap } from "./config/shared";

interface NodeConfigFormProps {
  type: string;
  config: Record<string, unknown>;
  datasets: Dataset[];
  projectId?: string | null;
  /** Columns available on the wire entering this node (for column pickers). */
  columns: string[];
  onChange: (config: Record<string, unknown>) => void;
  onErrors: (hasErrors: boolean) => void;
}

export function NodeConfigForm({
  type,
  config,
  datasets,
  projectId,
  columns,
  onChange,
  onErrors,
}: NodeConfigFormProps) {
  const [errors, setErrors] = useState<ErrorMap>({});

  // Validate the current config against the node's zod schema.
  useEffect(() => {
    const schema = getConfigSchema(type);
    const result = schema.safeParse(config);
    if (result.success) {
      setErrors({});
      onErrors(false);
    } else {
      const map: ErrorMap = {};
      for (const issue of result.error.issues) {
        const key = issue.path[0]?.toString() ?? "_";
        if (!map[key]) map[key] = issue.message;
      }
      setErrors(map);
      onErrors(true);
    }
    // By reference, not JSON.stringify: the editor store replaces the config
    // object on every edit, and stringifying on each sidebar render is wasted
    // work in a hot path (the sidebar re-renders with every store change).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [type, config]);

  const set = (patch: Record<string, unknown>) => onChange({ ...config, ...patch });
  const c = config as Record<string, any>;

  // Connection data for SQL/storage nodes (hooks must run unconditionally; the
  // table query is disabled unless this is a SQL node with a chosen connection).
  const { data: connections = [] } = useConnections();
  const isSqlNode = type === "sqlInput" || type === "sqlOutput";
  const isStorageInput = type === "storageInput";
  const tablesQuery = useConnectionTables(isSqlNode ? c.connection_id || null : null);
  const objectsQuery = useConnectionObjects(isStorageInput ? c.connection_id || null : null);

  // SQL nodes use database connections only — never storage or the MLflow
  // tracking connection (which isn't a queryable database). API connections are
  // readable (SQL Input) but read-only, so SQL Output excludes them.
  const sqlConnections = connections.filter(
    (cn) => cn.connection_type !== "storage" && cn.connection_type !== "mlflow",
  );
  const sqlWriteConnections = sqlConnections.filter((cn) => cn.connection_type !== "api");
  const storageConnections = connections.filter((cn) => cn.connection_type === "storage");

  const FILE_INPUT_SOURCE: Record<string, string> = {
    fileInput: "csv",
    csvInput: "csv",
    excelInput: "excel",
    parquetInput: "parquet",
    jsonInput: "json",
    textInput: "text",
  };
  if (type in FILE_INPUT_SOURCE) {
    const fileInputFormats = [
      { value: "csv", label: "CSV" },
      { value: "tsv", label: "TSV" },
      { value: "excel", label: "Excel" },
      { value: "parquet", label: "Parquet" },
      { value: "json", label: "JSON" },
      { value: "jsonl", label: "JSON Lines" },
      { value: "text", label: "Text" },
    ];
    const datasetSourceForFormat: Record<string, string> = {
      csv: "csv",
      tsv: "tsv",
      excel: "excel",
      parquet: "parquet",
      json: "json",
      jsonl: "jsonl",
      text: "text",
    };
    const isUnified = type === "fileInput";
    const format = isUnified ? String(c.format ?? "csv") : FILE_INPUT_SOURCE[type];
    const accepted = datasetSourceForFormat[format] ?? FILE_INPUT_SOURCE[type];
    const projectDatasets = projectId ? datasets.filter((d) => d.project_id === projectId) : datasets;
    const compatible = projectDatasets.filter((d) => d.source_type === accepted);
    const selected = projectDatasets.find((d) => d.id === c.dataset_id);
    const pinned = (c.dataset_version as number | null | undefined) ?? selected?.latest_version;
    const isOutdated =
      selected != null && pinned != null && pinned < selected.latest_version;

    return (
      <>
        {isUnified && (
          <Field
            label="File type"
            error={errors.format}
            help="How this uploaded dataset should be read at run time."
          >
            <Select
              value={format}
              onChange={(e) => set({ format: e.target.value, dataset_id: "", dataset_version: null })}
            >
              {fileInputFormats.map((f) => (
                <option key={f.value} value={f.value}>
                  {f.label}
                </option>
              ))}
            </Select>
          </Field>
        )}
        <Field
          label="Dataset"
          error={errors.dataset_id}
          help={
            isUnified
              ? `Only datasets compatible with ${format.toUpperCase()} are listed.`
              : `Only ${accepted.toUpperCase()} datasets can be loaded by this node.`
          }
        >
          <Select
            value={(c.dataset_id as string) ?? ""}
            onChange={(e) => {
              // Default to pinning the chosen dataset's latest version.
              const ds = projectDatasets.find((d) => d.id === e.target.value);
              set({ dataset_id: e.target.value, dataset_version: ds?.latest_version ?? null });
            }}
          >
            <option value="">Select a dataset…</option>
            {compatible.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}
              </option>
            ))}
          </Select>
          {compatible.length === 0 && (
            <p className="text-[11px] text-amber-600">
              No {accepted.toUpperCase()} datasets uploaded yet.
            </p>
          )}
        </Field>

        {selected && (
          <Field
            label="Version"
            help="Pin a specific version so scheduled runs always read the same data. New versions don't affect this flow until you update."
          >
            <Select
              value={String(pinned ?? selected.latest_version)}
              onChange={(e) => set({ dataset_version: Number(e.target.value) })}
            >
              {Array.from({ length: selected.latest_version }, (_, i) => selected.latest_version - i).map(
                (v) => (
                  <option key={v} value={v}>
                    v{v}
                    {v === selected.latest_version ? " (latest)" : ""}
                  </option>
                ),
              )}
            </Select>
            {isOutdated && (
              <p className="flex flex-wrap items-center gap-1 text-[11px] text-amber-600">
                Pinned to v{pinned}; v{selected.latest_version} is now available.
                <button
                  type="button"
                  className="font-medium text-primary underline underline-offset-2"
                  onClick={() => set({ dataset_version: selected.latest_version })}
                >
                  Update to latest
                </button>
              </p>
            )}
          </Field>
        )}
      </>
    );
  }

  switch (type) {
    case "dropNulls":
    case "fillNulls":
    case "dropColumns":
    case "selectColumns":
    case "renameColumns":
    case "removeDuplicates":
    case "filterRows":
    case "sortRows":
    case "castDtypes":
    case "limitRows":
    case "replaceValues":
    case "stringTransform":
    case "calculatedColumn":
      return renderCleaningConfig(type, { c, errors, set, columns });

    case "groupByAggregate":
    case "join":
    case "concatRows":
    case "sampleRows":
    case "removeOutliers":
    case "roundNumbers":
    case "binColumn":
    case "extractDateParts":
    case "unpivot":
    case "pivot":
    case "splitColumn":
    case "parseDates":
    case "mapValues":
    case "windowFunction":
    case "conditionalColumn":
      return renderReshapeConfig(type, { c, errors, set, columns });

    case "sqlInput": {
      const mode = (c.mode as string) ?? "table";
      const currentTable = c.schema ? `${c.schema}.${c.table}` : c.table;
      // API connections read HTTP endpoints as tables, so the copy adapts:
      // "Endpoint" instead of "Table", "Request path" instead of "Custom SQL".
      const isApiConnection =
        connections.find((cn) => cn.id === c.connection_id)?.connection_type === "api";
      const connectionPicker = (
        <Field label="Connection" error={errors.connection_id} help="Reusable database or API connection (manage these on the Connections page).">
          <Select
            value={c.connection_id ?? ""}
            onChange={(e) => set({ connection_id: e.target.value, table: "", schema: null })}
          >
            <option value="">Select a connection…</option>
            {sqlConnections.map((cn) => (
              <option key={cn.id} value={cn.id}>
                {cn.name}
              </option>
            ))}
          </Select>
          {sqlConnections.length === 0 && (
            <p className="text-[11px] text-amber-600">
              No database connections yet — add one on the Connections page.
            </p>
          )}
        </Field>
      );
      return (
        <>
          {connectionPicker}
          <Field
            label="Source"
            help={
              isApiConnection
                ? "Read a declared endpoint, or request a custom path."
                : "Read a whole table, or run a custom SQL query."
            }
          >
            <Select value={mode} onChange={(e) => set({ mode: e.target.value })}>
              <option value="table">{isApiConnection ? "Endpoint" : "Table"}</option>
              <option value="query">{isApiConnection ? "Custom request path" : "Custom SQL"}</option>
            </Select>
          </Field>
          {mode === "query" ? (
            <Field
              label={isApiConnection ? "Request path" : "SQL query"}
              error={errors.query}
              help={
                isApiConnection
                  ? "Relative to the connection's base URL; may include a query string."
                  : "Runs against the selected connection."
              }
            >
              <textarea
                className="min-h-[80px] w-full rounded-md border border-input bg-background px-2 py-1.5 text-xs font-mono focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                value={c.query ?? ""}
                onChange={(e) => set({ query: e.target.value })}
                placeholder={
                  isApiConnection ? "users?active=true" : "SELECT * FROM orders WHERE status = 'paid'"
                }
              />
            </Field>
          ) : (
            <Field
              label={isApiConnection ? "Endpoint" : "Table"}
              error={errors.table}
              help={
                isApiConnection
                  ? "Endpoints declared on the connection are listed here."
                  : "Tables are listed from the connection."
              }
            >
              {tablesQuery.data && tablesQuery.data.length > 0 ? (
                <Select
                  value={currentTable ?? ""}
                  onChange={(e) => {
                    const t = tablesQuery.data!.find((x) => x.qualified === e.target.value);
                    set({ table: t?.name ?? e.target.value, schema: t?.schema_name ?? null });
                  }}
                >
                  <option value="">{isApiConnection ? "Select an endpoint…" : "Select a table…"}</option>
                  {tablesQuery.data.map((t) => (
                    <option key={t.qualified} value={t.qualified}>
                      {t.qualified}
                    </option>
                  ))}
                </Select>
              ) : (
                <Input
                  value={c.table ?? ""}
                  onChange={(e) => set({ table: e.target.value })}
                  placeholder={isApiConnection ? "endpoint path" : "table name"}
                />
              )}
              {tablesQuery.isFetching && (
                <p className="text-[11px] text-muted-foreground">Loading tables…</p>
              )}
              {tablesQuery.isError && (
                <p className="text-[11px] text-amber-600">
                  Couldn't list tables — type the name manually.
                </p>
              )}
            </Field>
          )}
        </>
      );
    }

    case "sqlOutput":
      return (
        <>
          <Field label="Connection" error={errors.connection_id} help="Where to write the result. API connections are read-only and not listed.">
            <Select
              value={c.connection_id ?? ""}
              onChange={(e) => set({ connection_id: e.target.value })}
            >
              <option value="">Select a connection…</option>
              {sqlWriteConnections.map((cn) => (
                <option key={cn.id} value={cn.id}>
                  {cn.name}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Target table" error={errors.table} help="The table (or collection) to write to.">
            <Input
              value={c.table ?? ""}
              onChange={(e) => set({ table: e.target.value })}
              placeholder="cleaned_orders"
            />
          </Field>
          <Field label="If table exists" error={errors.if_exists} help="What to do when the target already exists.">
            <Select value={c.if_exists ?? "replace"} onChange={(e) => set({ if_exists: e.target.value })}>
              <option value="replace">Replace</option>
              <option value="append">Append</option>
              <option value="fail">Fail</option>
            </Select>
          </Field>
        </>
      );

    case "storageInput": {
      const SUPPORTED_EXTS = new Set(["csv", "xlsx", "xls", "parquet", "json", "txt"]);
      const allObjects = objectsQuery.data ?? [];
      const objects = allObjects.filter((obj) => {
        const ext = obj.split(".").pop()?.toLowerCase() ?? "";
        return SUPPORTED_EXTS.has(ext);
      });
      const selectedPath = (c.path as string) ?? "";
      const formatFromPath = (p: string): string => {
        const ext = p.split(".").pop()?.toLowerCase();
        if (ext === "parquet") return "parquet";
        if (ext === "xlsx" || ext === "xls") return "excel";
        if (ext === "json") return "json";
        if (ext === "txt") return "text";
        return "csv";
      };
      return (
        <>
          <Field label="Storage connection" error={errors.connection_id} help="S3, Azure Blob, GCS, or local folder (manage on the Connections page).">
            <Select
              value={c.connection_id ?? ""}
              onChange={(e) => set({ connection_id: e.target.value, path: "", format: "csv" })}
            >
              <option value="">Select a storage connection…</option>
              {storageConnections.map((cn) => (
                <option key={cn.id} value={cn.id}>
                  {cn.name}
                </option>
              ))}
            </Select>
            {storageConnections.length === 0 && (
              <p className="text-[11px] text-amber-600">
                No storage connections yet — add one on the Connections page.
              </p>
            )}
          </Field>
          {c.connection_id && (
            <Field
              label="File"
              error={errors.path}
              help="Select a file from the storage connection, or type a path manually."
            >
              {objectsQuery.isFetching ? (
                <p className="text-[11px] text-muted-foreground">Loading files…</p>
              ) : objects.length > 0 ? (
                <div className="flex flex-col gap-1">
                  <div className="max-h-40 overflow-y-auto rounded-md border border-input bg-background">
                    {objects.map((obj) => (
                      <button
                        key={obj}
                        type="button"
                        onClick={() => set({ path: obj, format: formatFromPath(obj) })}
                        className={cn(
                          "w-full px-2 py-1 text-left text-[11px] font-mono hover:bg-muted",
                          selectedPath === obj && "bg-primary/10 font-semibold text-primary",
                        )}
                      >
                        {obj}
                      </button>
                    ))}
                  </div>
                  {selectedPath && !objects.includes(selectedPath) && (
                    <p className="text-[11px] text-amber-600">
                      Current path not found in connection — update or retype below.
                    </p>
                  )}
                </div>
              ) : (
                <p className="text-[11px] text-muted-foreground">
                  No files found in this connection.
                </p>
              )}
              <Input
                className="mt-1"
                value={selectedPath}
                onChange={(e) => set({ path: e.target.value, format: formatFromPath(e.target.value) })}
                placeholder="data/input.csv"
              />
            </Field>
          )}
          <Field label="Format" error={errors.format} help="File format to read.">
            <Select value={c.format ?? "csv"} onChange={(e) => set({ format: e.target.value })}>
              <option value="csv">CSV</option>
              <option value="tsv">TSV</option>
              <option value="excel">Excel (.xlsx)</option>
              <option value="parquet">Parquet</option>
              <option value="json">JSON</option>
              <option value="jsonl">JSON Lines (.jsonl)</option>
              <option value="text">Text (one row per line)</option>
            </Select>
          </Field>
        </>
      );
    }

    case "storageOutput":
      return (
        <>
          <Field label="Storage connection" error={errors.connection_id} help="S3, Azure Blob, GCS, or local folder (manage on the Connections page).">
            <Select
              value={c.connection_id ?? ""}
              onChange={(e) => set({ connection_id: e.target.value })}
            >
              <option value="">Select a storage connection…</option>
              {storageConnections.map((cn) => (
                <option key={cn.id} value={cn.id}>
                  {cn.name}
                </option>
              ))}
            </Select>
            {storageConnections.length === 0 && (
              <p className="text-[11px] text-amber-600">
                No storage connections yet — add one on the Connections page.
              </p>
            )}
          </Field>
          <Field
            label="Destination path"
            error={errors.path}
            hint="e.g. outputs/result.parquet"
            help="Where the file is written within the bucket or folder."
          >
            <Input
              value={c.path ?? ""}
              onChange={(e) => set({ path: e.target.value })}
              placeholder="outputs/result.parquet"
            />
          </Field>
          <Field label="Format" error={errors.format} help="File format to write.">
            <Select value={c.format ?? "parquet"} onChange={(e) => set({ format: e.target.value })}>
              <option value="csv">CSV</option>
              <option value="tsv">TSV</option>
              <option value="excel">Excel (.xlsx)</option>
              <option value="parquet">Parquet</option>
              <option value="json">JSON</option>
              <option value="jsonl">JSON Lines (.jsonl)</option>
              <option value="text">Text (one row per line)</option>
            </Select>
          </Field>
          <Field label="If file exists" error={errors.if_exists} help="Overwrite the existing file, or fail if it already exists.">
            <Select value={c.if_exists ?? "overwrite"} onChange={(e) => set({ if_exists: e.target.value })}>
              <option value="overwrite">Overwrite</option>
              <option value="error">Fail with error</option>
            </Select>
          </Field>
        </>
      );

    case "fileOutput":
      return (
        <>
          <Field label="File type" help="The file format to write the result as.">
            <Select value={c.format ?? "csv"} onChange={(e) => set({ format: e.target.value })}>
              <option value="csv">CSV (.csv)</option>
              <option value="tsv">TSV (.tsv)</option>
              <option value="excel">Excel (.xlsx)</option>
              <option value="parquet">Parquet (.parquet)</option>
              <option value="json">JSON (.json)</option>
              <option value="jsonl">JSON Lines (.jsonl)</option>
              <option value="text">Text (.txt)</option>
            </Select>
          </Field>
          <Field
            label="Dataset name"
            hint="e.g. cleaned_sales"
            help="The output is saved as a reusable dataset in your project under this name. Re-running adds a new version."
            error={errors.dataset_name}
          >
            <Input
              value={c.dataset_name ?? ""}
              onChange={(e) => set({ dataset_name: e.target.value })}
              placeholder="my_output_dataset"
            />
          </Field>
        </>
      );

    case "csvOutput":
    case "excelOutput":
    case "parquetOutput":
      return (
        <Field
          label="Dataset name"
          hint="e.g. cleaned_sales"
          help="The output is saved as a reusable dataset in your project under this name. Re-running adds a new version."
          error={errors.dataset_name}
        >
          <Input
            value={c.dataset_name ?? ""}
            onChange={(e) => set({ dataset_name: e.target.value })}
            placeholder="my_output_dataset"
          />
        </Field>
      );

    // ----- Machine learning -----
    case "mlClassifierModel":
    case "mlRegressorModel":
    case "mlTrainClassifier":
    case "mlTrainRegressor":
    case "mlTrainClustering":
    case "mlTrainForecaster":
    case "mlTrainDimReduction":
    case "mlCrossValidate":
    case "trainTestSplit":
    case "scaleFeatures":
    case "encodeCategories":
    case "selectFeatures":
    case "reduceDimensions":
    case "mlPredict":
    case "mlEvaluate":
    case "featureImportance":
      return renderMlConfig(type, { c, errors, set, columns });

    // ----- Advanced -----
    case "pythonTransform":
      return (
        <Field
          label="Script"
          error={errors.script}
          help="Write the body of def transform(df): … — must return a DataFrame. Use 'pd' (pandas engine) or 'pl' (polars engine) without importing them."
        >
          <textarea
            className="w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-xs leading-relaxed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            rows={10}
            spellCheck={false}
            value={(c.script as string) ?? ""}
            placeholder={"# pandas example\nreturn df[df['column'] > 0]\n\n# polars example\nreturn df.filter(pl.col('column') > 0)"}
            onChange={(e) => set({ script: e.target.value })}
          />
        </Field>
      );

    // ----- Charts -----
    case "chartBar":
    case "chartLine":
    case "chartArea":
    case "chartScatter":
    case "chartPie":
    case "chartHistogram":
    case "chartBoxPlot":
    case "chartHeatmap":
      return renderChartConfig(type, { c, errors, set, columns });

    // ----- Data Quality -----
    case "assertNotNull":
    case "assertUnique":
    case "assertValueRange":
    case "assertExpression":
    case "assertRowCount":
    case "assertValuesInSet":
    case "filterExpression":
      return renderQualityConfig(type, { c, errors, set, columns });

    case "combineColumns":
    case "coalesceColumns":
    case "explodeRows":
    case "rollingAggregate":
    case "rowDifference":
    case "dateDifference":
      return renderReshapeConfig(type, { c, errors, set, columns });

    default: {
      // Plugin nodes: render the schema-driven form the plugin declared
      // (config_schema), or fall back to fields inferred from its default
      // config so every plugin node stays configurable without a hand-written
      // form here.
      const def = getNodeTypeDef(type);
      const schemaFields = def?.configSchema?.length
        ? def.configSchema
        : def && Object.keys(def.defaultConfig ?? {}).length
          ? fieldsFromDefaults(def.defaultConfig)
          : null;
      if (schemaFields) {
        return (
          <SchemaConfigFields
            fields={schemaFields}
            config={c}
            columns={columns}
            errors={errors}
            onChange={(key, value) => set({ [key]: value })}
          />
        );
      }
      return <p className="text-xs text-muted-foreground">No configuration for this node type.</p>;
    }
  }
}

