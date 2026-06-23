import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { TooltipProvider } from "@/components/ui/tooltip";
import { NodeConfigForm } from "../NodeConfigForm";

const testQueryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });

function renderForm(props: Partial<React.ComponentProps<typeof NodeConfigForm>>) {
  return render(
    <QueryClientProvider client={testQueryClient}>
      <TooltipProvider>
        <NodeConfigForm
          type="scaleFeatures"
          config={{}}
          datasets={[]}
          columns={[]}
          onChange={() => {}}
          onErrors={() => {}}
          {...props}
        />
      </TooltipProvider>
    </QueryClientProvider>,
  );
}

describe("ML node config forms", () => {
  it("trainTestSplit edits test_size, stratify, and seed", () => {
    const onChange = vi.fn();
    renderForm({
      type: "trainTestSplit",
      config: { test_size: 0.2, stratify_column: null, seed: 42 },
      columns: ["a", "target"],
      onChange,
    });
    // stratify offers the upstream columns
    const options = screen.getAllByRole("option").map((o) => o.textContent);
    expect(options).toContain("target");
    // editing the seed propagates a number
    const seed = screen.getByDisplayValue("42");
    fireEvent.change(seed, { target: { value: "7" } });
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ seed: 7 }));
  });

  it("scaleFeatures renders column chips and a method select", () => {
    renderForm({ type: "scaleFeatures", config: { method: "standard", columns: [] }, columns: ["x", "y"] });
    expect(screen.getByRole("button", { name: "x" })).toBeInTheDocument();
    const options = screen.getAllByRole("option").map((o) => o.textContent);
    expect(options).toContain("Robust (median / IQR)");
  });

  it("encodeCategories shows drop-first only for one-hot", () => {
    const { rerender } = renderForm({
      type: "encodeCategories",
      config: { method: "onehot", columns: ["c"] },
      columns: ["c"],
    });
    expect(screen.getByText(/Drop the first category/i)).toBeInTheDocument();
    rerender(
      <QueryClientProvider client={testQueryClient}>
        <TooltipProvider>
          <NodeConfigForm
            type="encodeCategories"
            config={{ method: "ordinal", columns: ["c"] }}
            datasets={[]}
            columns={["c"]}
            onChange={() => {}}
            onErrors={() => {}}
          />
        </TooltipProvider>
      </QueryClientProvider>,
    );
    expect(screen.queryByText(/Drop the first category/i)).not.toBeInTheDocument();
  });

  it("selectFeatures swaps threshold for target+K under kbest", () => {
    const { rerender } = renderForm({
      type: "selectFeatures",
      config: { method: "variance", threshold: 0 },
      columns: ["a", "y"],
    });
    expect(screen.getByText("Threshold")).toBeInTheDocument();
    rerender(
      <QueryClientProvider client={testQueryClient}>
        <TooltipProvider>
          <NodeConfigForm
            type="selectFeatures"
            config={{ method: "kbest", target_column: "", k: 10 }}
            datasets={[]}
            columns={["a", "y"]}
            onChange={() => {}}
            onErrors={() => {}}
          />
        </TooltipProvider>
      </QueryClientProvider>,
    );
    expect(screen.getByText("Target column")).toBeInTheDocument();
    expect(screen.getByText(/Keep top K/i)).toBeInTheDocument();
  });

  it("mlEvaluate hides the target column for clustering", () => {
    const { rerender } = renderForm({
      type: "mlEvaluate",
      config: { task_type: "classification", target_column: "", prediction_column: "prediction" },
      columns: ["y", "prediction"],
    });
    expect(screen.getByText("True value column")).toBeInTheDocument();
    rerender(
      <QueryClientProvider client={testQueryClient}>
        <TooltipProvider>
          <NodeConfigForm
            type="mlEvaluate"
            config={{ task_type: "clustering", prediction_column: "cluster" }}
            datasets={[]}
            columns={["cluster"]}
            onChange={() => {}}
            onErrors={() => {}}
          />
        </TooltipProvider>
      </QueryClientProvider>,
    );
    expect(screen.queryByText("True value column")).not.toBeInTheDocument();
    expect(screen.getByText("Cluster label column")).toBeInTheDocument();
  });

  it("mlPredict names the prediction column", () => {
    const onChange = vi.fn();
    renderForm({
      type: "mlPredict",
      config: { output_column: "prediction", output_proba_columns: [] },
      columns: ["a"],
      onChange,
    });
    const input = screen.getByDisplayValue("prediction");
    fireEvent.change(input, { target: { value: "yhat" } });
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ output_column: "yhat" }));
  });

  it("featureImportance clears top_n to null when emptied", () => {
    const onChange = vi.fn();
    renderForm({ type: "featureImportance", config: { top_n: 5 }, columns: [], onChange });
    const input = screen.getByDisplayValue("5");
    fireEvent.change(input, { target: { value: "" } });
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ top_n: null }));
  });
});

describe("mlTrain config form", () => {
  const baseConfig = {
    model_type: "random_forest_classifier",
    target_column: "",
    feature_columns: [],
    hyperparameters: {},
    seed: 42,
  };

  it("shows the target picker for supervised models", () => {
    renderForm({ type: "mlTrain", config: baseConfig, columns: ["a", "target"] });
    expect(screen.getByText("Target column")).toBeInTheDocument();
  });

  it("hides the target picker for unsupervised models", () => {
    renderForm({
      type: "mlTrain",
      config: { ...baseConfig, model_type: "kmeans" },
      columns: ["a", "b"],
    });
    expect(screen.queryByText("Target column")).not.toBeInTheDocument();
  });

  it("resets hyperparameters when the model changes", () => {
    const onChange = vi.fn();
    renderForm({
      type: "mlTrain",
      config: { ...baseConfig, hyperparameters: { n_estimators: 500 } },
      columns: ["a"],
      onChange,
    });
    const modelSelect = screen.getByDisplayValue("Random Forest");
    fireEvent.change(modelSelect, { target: { value: "ridge" } });
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ model_type: "ridge", hyperparameters: {} }),
    );
  });

  it("writes a hyperparameter change", () => {
    const onChange = vi.fn();
    renderForm({ type: "mlTrain", config: baseConfig, columns: ["a"], onChange });
    // Random Forest's basic param: "Number of trees" (n_estimators, default 100)
    const trees = screen.getByDisplayValue("100");
    fireEvent.change(trees, { target: { value: "250" } });
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ hyperparameters: { n_estimators: 250 } }),
    );
  });

  it("warns when a model needs an extra library", () => {
    renderForm({
      type: "mlTrain",
      config: { ...baseConfig, model_type: "xgboost_classifier" },
      columns: ["a"],
    });
    expect(screen.getByText(/Needs the/i)).toBeInTheDocument();
  });

  it("opens the Advanced options modal with cross-validation", () => {
    renderForm({ type: "mlTrain", config: baseConfig, columns: ["a"] });
    fireEvent.click(screen.getByRole("button", { name: /Advanced options/i }));
    expect(screen.getByText("Cross-validation")).toBeInTheDocument();
    expect(screen.getByText("Preprocessing")).toBeInTheDocument();
  });
});
