import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { TooltipProvider } from "@/components/ui/tooltip";
import { NodeConfigForm } from "../NodeConfigForm";
import type { Dataset } from "@/features/datasets/types";

function dataset(id: string, source: Dataset["source_type"], projectId: string | null = null): Dataset {
  return {
    id,
    name: `${id}.${source}`,
    source_type: source,
    dataset_kind: "input",
    is_disabled: false,
    project_id: projectId,
    latest_version: 1,
    version_count: 1,
    column_schema: [{ name: "a", type: "string" }],
    data_sample: [],
    column_profile: null,
    created_at: "",
    updated_at: "",
  };
}

// The form reads connections via TanStack Query, so every render needs a client.
const testQueryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });

function Wrap({ children }: { children: React.ReactNode }) {
  return (
    <QueryClientProvider client={testQueryClient}>
      <TooltipProvider>{children}</TooltipProvider>
    </QueryClientProvider>
  );
}

function renderForm(props: Partial<React.ComponentProps<typeof NodeConfigForm>>) {
  return render(
    <Wrap>
      <NodeConfigForm
        type="dropColumns"
        config={{}}
        datasets={[]}
        columns={[]}
        onChange={() => {}}
        onErrors={() => {}}
        {...props}
      />
    </Wrap>,
  );
}

describe("NodeConfigForm", () => {
  it("only offers datasets matching the input node's source type", () => {
    const csv = dataset("sales", "csv");
    const excel = dataset("report", "excel");
    renderForm({
      type: "excelInput",
      config: { dataset_id: "" },
      datasets: [csv, excel],
    });

    const options = screen.getAllByRole("option").map((o) => o.textContent);
    expect(options).toContain("report.excel");
    expect(options).not.toContain("sales.csv");
  });

  it("filters File Input datasets by selected file type and clears stale dataset on type change", () => {
    const onChange = vi.fn();
    renderForm({
      type: "fileInput",
      config: { dataset_id: "sales", dataset_version: 1, format: "csv" },
      datasets: [dataset("sales", "csv"), dataset("warehouse", "parquet")],
      onChange,
    });

    const options = screen.getAllByRole("option").map((o) => o.textContent);
    expect(options).toContain("sales.csv");
    expect(options).not.toContain("warehouse.parquet");

    fireEvent.change(screen.getAllByRole("combobox")[0], { target: { value: "parquet" } });
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ format: "parquet", dataset_id: "", dataset_version: null }),
    );
  });

  it("offers compatible datasets for File Input parquet format", () => {
    renderForm({
      type: "fileInput",
      config: { dataset_id: "", format: "parquet" },
      datasets: [dataset("sales", "csv"), dataset("warehouse", "parquet")],
    });
    const options = screen.getAllByRole("option").map((o) => o.textContent);
    expect(options).toContain("warehouse.parquet");
    expect(options).not.toContain("sales.csv");
  });

  it("filters File Input datasets by exact TSV and JSONL source types", () => {
    const { rerender } = render(
      <Wrap>
        <NodeConfigForm
          type="fileInput"
          config={{ dataset_id: "", format: "tsv" }}
          datasets={[dataset("sales", "csv"), dataset("events", "tsv")]}
          columns={[]}
          onChange={() => {}}
          onErrors={() => {}}
        />
      </Wrap>,
    );

    let options = screen.getAllByRole("option").map((o) => o.textContent);
    expect(options).toContain("events.tsv");
    expect(options).not.toContain("sales.csv");

    rerender(
      <Wrap>
        <NodeConfigForm
          type="fileInput"
          config={{ dataset_id: "", format: "jsonl" }}
          datasets={[dataset("payloads", "json"), dataset("stream", "jsonl")]}
          columns={[]}
          onChange={() => {}}
          onErrors={() => {}}
        />
      </Wrap>,
    );

    options = screen.getAllByRole("option").map((o) => o.textContent);
    expect(options).toContain("stream.jsonl");
    expect(options).not.toContain("payloads.json");
  });

  it("limits File Input datasets to the active project", () => {
    renderForm({
      type: "fileInput",
      config: { dataset_id: "", format: "csv" },
      projectId: "p1",
      datasets: [
        dataset("sales", "csv", "p1"),
        dataset("other-project", "csv", "p2"),
        dataset("report", "excel", "p1"),
      ],
    });

    const options = screen.getAllByRole("option").map((o) => o.textContent);
    expect(options).toContain("sales.csv");
    expect(options).not.toContain("other-project.csv");
    expect(options).not.toContain("report.excel");
  });

  it("warns when no compatible dataset exists for an input node", () => {
    renderForm({
      type: "parquetInput",
      config: { dataset_id: "" },
      datasets: [dataset("sales", "csv")],
    });
    expect(screen.getByText(/No PARQUET datasets uploaded yet/i)).toBeInTheDocument();
  });

  it("renders column chips when upstream columns are known", () => {
    renderForm({
      type: "dropColumns",
      config: { columns: [] },
      columns: ["name", "age"],
    });
    expect(screen.getByRole("button", { name: "name" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "age" })).toBeInTheDocument();
  });

  it("offers a column dropdown for Change Type when columns are known", () => {
    renderForm({
      type: "castDtypes",
      config: { casts: {} },
      columns: ["name", "age"],
    });
    // The add-column select exposes the upstream columns as options.
    const options = screen.getAllByRole("option").map((o) => o.textContent);
    expect(options).toContain("name");
    expect(options).toContain("age");
    expect(options).toContain("+ Add column…");
  });

  it("fills the formula from a template using upstream column names", () => {
    const onChange = vi.fn();
    renderForm({
      type: "calculatedColumn",
      config: { column_name: "total", expression: "" },
      columns: ["price", "quantity"],
      onChange,
    });
    const templateSelect = screen.getAllByRole("combobox")[0];
    fireEvent.change(templateSelect, { target: { value: "Product" } });
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ expression: "price * quantity" }),
    );
  });

  it("falls back to a connect hint when no columns are known", () => {
    renderForm({
      type: "filterRows",
      config: { column: "", operator: "==", value: "" },
      columns: [],
    });
    expect(screen.getByText(/Connect an upstream input/i)).toBeInTheDocument();
  });

  it("hides the fill value input unless the constant strategy is selected", () => {
    const onChange = vi.fn();
    const { rerender } = render(
      <Wrap>
        <NodeConfigForm
          type="fillNulls"
          config={{ strategy: "constant", value: "", columns: [] }}
          datasets={[]}
          columns={["a"]}
          onChange={onChange}
          onErrors={() => {}}
        />
      </Wrap>,
    );
    expect(screen.getByText("Fill value")).toBeInTheDocument();

    // Switch to mean → the constant value input disappears.
    rerender(
      <Wrap>
        <NodeConfigForm
          type="fillNulls"
          config={{ strategy: "mean", value: "", columns: [] }}
          datasets={[]}
          columns={["a"]}
          onChange={onChange}
          onErrors={() => {}}
        />
      </Wrap>,
    );
    expect(screen.queryByText("Fill value")).not.toBeInTheDocument();
  });

  it("shows an upper-bound field for the 'between' filter operator", () => {
    renderForm({
      type: "filterRows",
      config: { column: "a", operator: "between", value: "1", value2: "9" },
      columns: ["a"],
    });
    expect(screen.getByText("From (lower bound)")).toBeInTheDocument();
    expect(screen.getByText("To (upper bound)")).toBeInTheDocument();
  });

  it("builds a filter expression from guided controls", () => {
    const onChange = vi.fn();
    renderForm({
      type: "filterExpression",
      config: { expression: "" },
      columns: ["amount", "status"],
      onChange,
    });
    const selects = screen.getAllByRole("combobox");
    fireEvent.change(selects[0], { target: { value: "amount" } });
    fireEvent.change(selects[1], { target: { value: ">=" } });
    fireEvent.change(screen.getByPlaceholderText("value"), { target: { value: "100" } });
    fireEvent.click(screen.getByRole("button", { name: "Use condition" }));
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ expression: "amount >= 100" }));
  });

  it("shows method-specific fields for Remove Outliers", () => {
    const { rerender } = render(
      <Wrap>
        <NodeConfigForm
          type="removeOutliers"
          config={{ columns: ["a"], method: "iqr", action: "drop" }}
          datasets={[]}
          columns={["a"]}
          onChange={() => {}}
          onErrors={() => {}}
        />
      </Wrap>,
    );
    expect(screen.getByText("IQR factor")).toBeInTheDocument();
    expect(screen.queryByText("Lower percentile")).not.toBeInTheDocument();

    rerender(
      <Wrap>
        <NodeConfigForm
          type="removeOutliers"
          config={{ columns: ["a"], method: "percentile", action: "clip" }}
          datasets={[]}
          columns={["a"]}
          onChange={() => {}}
          onErrors={() => {}}
        />
      </Wrap>,
    );
    expect(screen.getByText("Lower percentile")).toBeInTheDocument();
    expect(screen.queryByText("IQR factor")).not.toBeInTheDocument();
  });

  it("shows pad fields only for the 'pad' string operation", () => {
    renderForm({
      type: "stringTransform",
      config: { column: "a", operation: "pad", width: 5 },
      columns: ["a"],
    });
    expect(screen.getByText("Target width")).toBeInTheDocument();
    expect(screen.getByText("Fill character")).toBeInTheDocument();
  });

  it("renders date-part chips for Extract Date Parts", () => {
    renderForm({
      type: "extractDateParts",
      config: { column: "d", parts: ["year"] },
      columns: ["d"],
    });
    expect(screen.getByRole("button", { name: "year" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "month" })).toBeInTheDocument();
  });

  it("selecting a chip reports the chosen column", () => {
    const onChange = vi.fn();
    renderForm({
      type: "dropColumns",
      config: { columns: [] },
      columns: ["name", "age"],
      onChange,
    });
    screen.getByRole("button", { name: "age" }).click();
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ columns: ["age"] }));
  });

  it("shows the target field only for value-based window functions", () => {
    const { rerender } = render(
      <Wrap>
        <NodeConfigForm
          type="windowFunction"
          config={{ function: "row_number", new_column: "rn" }}
          datasets={[]}
          columns={["amount"]}
          onChange={() => {}}
          onErrors={() => {}}
        />
      </Wrap>,
    );
    expect(screen.queryByText("Target column")).not.toBeInTheDocument();
    expect(screen.queryByText("Offset")).not.toBeInTheDocument();

    // cumsum operates on a value column → the target field appears.
    rerender(
      <Wrap>
        <NodeConfigForm
          type="windowFunction"
          config={{ function: "cumsum", target: "amount", new_column: "rt" }}
          datasets={[]}
          columns={["amount"]}
          onChange={() => {}}
          onErrors={() => {}}
        />
      </Wrap>,
    );
    expect(screen.getByText("Target column")).toBeInTheDocument();

    // lag/lead additionally expose an offset field.
    rerender(
      <Wrap>
        <NodeConfigForm
          type="windowFunction"
          config={{ function: "lag", target: "amount", offset: 1, new_column: "prev" }}
          datasets={[]}
          columns={["amount"]}
          onChange={() => {}}
          onErrors={() => {}}
        />
      </Wrap>,
    );
    expect(screen.getByText("Target column")).toBeInTheDocument();
    expect(screen.getByText("Offset")).toBeInTheDocument();
  });

  it("renders the key inputs for Bin Column", () => {
    renderForm({
      type: "binColumn",
      config: { column: "age", new_column: "bucket", method: "equalwidth", bins: 4 },
      columns: ["age"],
    });
    expect(screen.getByText("New column")).toBeInTheDocument();
    expect(screen.getByText("Method")).toBeInTheDocument();
    expect(screen.getByText("Number of bins")).toBeInTheDocument();
    expect(screen.getByText("Custom labels (optional)")).toBeInTheDocument();
  });

  it("lets Bin Column set custom bin labels", () => {
    const onChange = vi.fn();
    renderForm({
      type: "binColumn",
      config: { column: "total_spent", new_column: "tier", method: "quantile", bins: 3 },
      columns: ["total_spent"],
      onChange,
    });
    fireEvent.change(screen.getByPlaceholderText("Bronze, Silver, Gold"), {
      target: { value: "Bronze, Silver, Gold" },
    });
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ labels: ["Bronze", "Silver", "Gold"] }),
    );
  });

  it("renders pivot's index, columns, values and aggregation fields", () => {
    renderForm({
      type: "pivot",
      config: { index: ["id"], columns: "metric", values: "amount", aggfunc: "sum" },
      columns: ["id", "metric", "amount"],
    });
    expect(screen.getByText("Index columns")).toBeInTheDocument();
    expect(screen.getByText("Columns from")).toBeInTheDocument();
    expect(screen.getByText("Values from")).toBeInTheDocument();
    expect(screen.getByText("Aggregation")).toBeInTheDocument();
  });

  it("renders unpivot's id/value and naming fields", () => {
    renderForm({
      type: "unpivot",
      config: { id_vars: ["id"] },
      columns: ["id", "jan", "feb"],
    });
    expect(screen.getByText("Keep columns (id)")).toBeInTheDocument();
    expect(screen.getByText(/Unpivot columns/i)).toBeInTheDocument();
    expect(screen.getByText("Variable column name")).toBeInTheDocument();
    expect(screen.getByText("Value column name")).toBeInTheDocument();
  });

  it("reveals the default value input only when 'use default' is checked", () => {
    const { rerender } = render(
      <Wrap>
        <NodeConfigForm
          type="mapValues"
          config={{ column: "a", mapping: { yes: "1" }, use_default: false }}
          datasets={[]}
          columns={["a"]}
          onChange={() => {}}
          onErrors={() => {}}
        />
      </Wrap>,
    );
    expect(screen.queryByText("Default value")).not.toBeInTheDocument();

    rerender(
      <Wrap>
        <NodeConfigForm
          type="mapValues"
          config={{ column: "a", mapping: { yes: "1" }, use_default: true, default: "0" }}
          datasets={[]}
          columns={["a"]}
          onChange={() => {}}
          onErrors={() => {}}
        />
      </Wrap>,
    );
    expect(screen.getByText("Default value")).toBeInTheDocument();
  });

  it("swaps the delimiter and pattern inputs for Split Column", () => {
    const { rerender } = render(
      <Wrap>
        <NodeConfigForm
          type="splitColumn"
          config={{ column: "name", mode: "delimiter", delimiter: " ", into: ["a", "b"] }}
          datasets={[]}
          columns={["name"]}
          onChange={() => {}}
          onErrors={() => {}}
        />
      </Wrap>,
    );
    // "Delimiter" also appears as a <Select> option, so target the field label.
    expect(screen.getByText("Delimiter", { selector: "label" })).toBeInTheDocument();
    expect(screen.queryByText("Pattern", { selector: "label" })).not.toBeInTheDocument();

    rerender(
      <Wrap>
        <NodeConfigForm
          type="splitColumn"
          config={{ column: "name", mode: "regex", pattern: "(\\d+)", into: ["a"] }}
          datasets={[]}
          columns={["name"]}
          onChange={() => {}}
          onErrors={() => {}}
        />
      </Wrap>,
    );
    expect(screen.getByText("Pattern", { selector: "label" })).toBeInTheDocument();
    expect(screen.queryByText("Delimiter", { selector: "label" })).not.toBeInTheDocument();
  });

  it("toggles between row-count and fraction inputs for Sample Rows", () => {
    const { rerender } = render(
      <Wrap>
        <NodeConfigForm
          type="sampleRows"
          config={{ n: 100 }}
          datasets={[]}
          columns={["a"]}
          onChange={() => {}}
          onErrors={() => {}}
        />
      </Wrap>,
    );
    // "Row count" / "Fraction" are also <Select> options, so target field labels.
    expect(screen.getByText("Number of rows", { selector: "label" })).toBeInTheDocument();
    expect(screen.queryByText("Fraction", { selector: "label" })).not.toBeInTheDocument();

    rerender(
      <Wrap>
        <NodeConfigForm
          type="sampleRows"
          config={{ frac: 0.1 }}
          datasets={[]}
          columns={["a"]}
          onChange={() => {}}
          onErrors={() => {}}
        />
      </Wrap>,
    );
    expect(screen.getByText("Fraction", { selector: "label" })).toBeInTheDocument();
    expect(screen.queryByText("Number of rows", { selector: "label" })).not.toBeInTheDocument();
  });

  it("shows split-key inputs when join keys have different names", () => {
    const { rerender } = render(
      <Wrap>
        <NodeConfigForm
          type="join"
          config={{ on: "id", how: "inner" }}
          datasets={[]}
          columns={["id"]}
          onChange={() => {}}
          onErrors={() => {}}
        />
      </Wrap>,
    );
    expect(screen.getByText("Join on")).toBeInTheDocument();
    expect(screen.queryByText("Left key(s)")).not.toBeInTheDocument();

    rerender(
      <Wrap>
        <NodeConfigForm
          type="join"
          config={{ left_on: ["id"], right_on: ["ref"], how: "inner" }}
          datasets={[]}
          columns={["id", "ref"]}
          onChange={() => {}}
          onErrors={() => {}}
        />
      </Wrap>,
    );
    expect(screen.getByText("Left key(s)")).toBeInTheDocument();
    expect(screen.getByText("Right key(s)")).toBeInTheDocument();
    expect(screen.queryByText("Join on")).not.toBeInTheDocument();
  });

  it("swaps the table picker for a SQL query box in query mode", () => {
    const { rerender } = render(
      <Wrap>
        <NodeConfigForm
          type="sqlInput"
          config={{ connection_id: "c1", mode: "table", table: "orders" }}
          datasets={[]}
          columns={[]}
          onChange={() => {}}
          onErrors={() => {}}
        />
      </Wrap>,
    );
    // "Table" also appears as a <Select> option, so target the field label.
    expect(screen.getByText("Table", { selector: "label" })).toBeInTheDocument();
    expect(screen.queryByText("SQL query")).not.toBeInTheDocument();

    rerender(
      <Wrap>
        <NodeConfigForm
          type="sqlInput"
          config={{ connection_id: "c1", mode: "query", query: "SELECT 1" }}
          datasets={[]}
          columns={[]}
          onChange={() => {}}
          onErrors={() => {}}
        />
      </Wrap>,
    );
    expect(screen.getByText("SQL query")).toBeInTheDocument();
    expect(screen.queryByText("Table", { selector: "label" })).not.toBeInTheDocument();
  });

  it("renders the rule editor for Conditional Column", () => {
    renderForm({
      type: "conditionalColumn",
      config: {
        new_column: "tier",
        rules: [{ column: "amount", operator: ">=", value: "100", result: "high" }],
      },
      columns: ["amount"],
    });
    expect(screen.getByText("New column")).toBeInTheDocument();
    expect(screen.getByText(/Rules \(first match wins\)/i)).toBeInTheDocument();
    expect(screen.getByText("Default (else)")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /\+ Add rule/i })).toBeInTheDocument();
    expect(screen.getByPlaceholderText("then result →")).toBeInTheDocument();
  });

  it("renders the static concat hint with no fields", () => {
    renderForm({ type: "concatRows", config: {}, columns: ["a"] });
    expect(screen.getByText(/Stacks all incoming dataframes vertically/i)).toBeInTheDocument();
  });

  it("renders a dataset-name field for file output nodes", () => {
    renderForm({ type: "csvOutput", config: { dataset_name: "out" }, columns: ["a"] });
    expect(screen.getByText("Dataset name")).toBeInTheDocument();
  });
});

describe("NodeConfigForm plugin nodes", () => {
  it("renders a schema-driven form for a plugin node with config_schema", async () => {
    const { setRuntimeNodeDefs, clearRuntimeNodeDefs, NODE_TYPES } = await import("@/lib/nodeCatalog");
    setRuntimeNodeDefs([
      ...NODE_TYPES,
      {
        type: "rest.fetch",
        label: "REST Fetch",
        category: "plugins" as never,
        provider: "community.rest",
        defaultConfig: { path: "" },
        inputHandles: ["in"],
        hasOutput: true,
        description: "",
        configSchema: [
          { key: "path", label: "Endpoint path", type: "string", required: true },
          { key: "flatten", type: "boolean", default: false },
        ],
      },
    ]);
    try {
      renderForm({ type: "rest.fetch", config: {}, columns: ["a"] });
      expect(screen.getByText("Endpoint path *")).toBeInTheDocument();
      expect(screen.getByRole("checkbox")).toBeInTheDocument();
      expect(
        screen.queryByText(/No configuration for this node type/i),
      ).not.toBeInTheDocument();
    } finally {
      clearRuntimeNodeDefs();
    }
  });

  it("falls back to fields inferred from default_config without a schema", async () => {
    const { setRuntimeNodeDefs, clearRuntimeNodeDefs, NODE_TYPES } = await import("@/lib/nodeCatalog");
    setRuntimeNodeDefs([
      ...NODE_TYPES,
      {
        type: "hello.greeting",
        label: "Greeting",
        category: "plugins" as never,
        provider: "community.hello",
        defaultConfig: { column: "greeting", name: "world" },
        inputHandles: ["in"],
        hasOutput: true,
        description: "",
      },
    ]);
    try {
      const onChange = vi.fn();
      renderForm({ type: "hello.greeting", config: {}, columns: [], onChange });
      expect(screen.getByText("column")).toBeInTheDocument();
      expect(screen.getByText("name")).toBeInTheDocument();
      const inputs = screen.getAllByRole("textbox");
      fireEvent.change(inputs[1], { target: { value: "Ciaren" } });
      expect(onChange).toHaveBeenCalledWith({ name: "Ciaren" });
    } finally {
      clearRuntimeNodeDefs();
    }
  });

  it("keeps the no-configuration message for unknown node types", () => {
    renderForm({ type: "totally.unknown", config: {}, columns: [] });
    expect(screen.getByText(/No configuration for this node type/i)).toBeInTheDocument();
  });
});
