import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { cn } from "@/lib/utils";
import { Field } from "../configFields";
import type { Connection } from "@/features/connections/types";
import type { useConnectionObjects, useConnectionTables } from "@/features/connections/hooks";
import type { NodeConfigRenderProps } from "./shared";

// SQL/storage nodes are the one family that can't be pure closures: their
// table/object pickers depend on live connection queries, whose hooks must
// run unconditionally in NodeConfigForm's body (not inside a switch case) —
// so the query results/derived connection lists are threaded in as props
// instead of being recomputed here.
export interface IoConfigRenderProps extends NodeConfigRenderProps {
  connections: Connection[];
  sqlConnections: Connection[];
  sqlWriteConnections: Connection[];
  storageConnections: Connection[];
  tablesQuery: ReturnType<typeof useConnectionTables>;
  objectsQuery: ReturnType<typeof useConnectionObjects>;
}

export function renderIoConfig(type: string, ctx: IoConfigRenderProps) {
  const { c, errors, set, connections, sqlConnections, sqlWriteConnections, storageConnections, tablesQuery, objectsQuery } = ctx;

  switch (type) {
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

    default:
      return undefined;
  }
}
