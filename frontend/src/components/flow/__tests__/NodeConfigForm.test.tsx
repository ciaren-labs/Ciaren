import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { TooltipProvider } from "@/components/ui/tooltip";
import { NodeConfigForm } from "../NodeConfigForm";
import type { Dataset } from "@/lib/types";

function dataset(id: string, source: Dataset["source_type"]): Dataset {
  return {
    id,
    name: `${id}.${source}`,
    source_type: source,
    column_schema: [{ name: "a", type: "string" }],
    data_sample: [],
    created_at: "",
    updated_at: "",
  };
}

function renderForm(props: Partial<React.ComponentProps<typeof NodeConfigForm>>) {
  return render(
    <TooltipProvider>
      <NodeConfigForm
        type="dropColumns"
        config={{}}
        datasets={[]}
        columns={[]}
        onChange={() => {}}
        onErrors={() => {}}
        {...props}
      />
    </TooltipProvider>,
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
});
