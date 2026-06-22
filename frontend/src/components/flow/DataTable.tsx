interface DataTableProps {
  columns: string[];
  rows: Record<string, unknown>[];
}

function renderCell(value: unknown): string {
  if (value === null || value === undefined) return "";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

export function DataTable({ columns, rows }: DataTableProps) {
  if (columns.length === 0) {
    return (
      <p className="p-3 text-sm text-muted-foreground">No columns to display.</p>
    );
  }
  return (
    <div className="overflow-auto">
      <table className="border-collapse text-xs">
        <thead className="sticky top-0 bg-muted">
          <tr>
            {columns.map((col) => (
              <th
                key={col}
                className="border-b border-border px-2 py-1 text-left font-semibold"
              >
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} className="odd:bg-background even:bg-muted/30">
              {columns.map((col) => (
                <td
                  key={col}
                  className="max-w-[220px] truncate border-b border-border px-2 py-1"
                  title={renderCell(row[col])}
                >
                  {renderCell(row[col])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {rows.length === 0 && (
        <p className="p-3 text-sm text-muted-foreground">No rows.</p>
      )}
    </div>
  );
}
