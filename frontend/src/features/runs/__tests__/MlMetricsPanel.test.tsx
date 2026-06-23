import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MlMetricsPanel } from "../MlMetricsPanel";
import type { NodeResult } from "@/lib/types";

const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });

function result(overrides: Partial<NodeResult>): NodeResult {
  return {
    node_id: "n",
    type: "mlTrain",
    label: "Train",
    status: "success",
    rows: 100,
    columns: [],
    sample: [],
    error: null,
    ml_metrics: null,
    mlflow_run_id: null,
    model_uri: null,
    task_type: null,
    cv_scores: null,
    ...overrides,
  };
}

function renderPanel(r: NodeResult) {
  return render(
    <QueryClientProvider client={client}>
      <MlMetricsPanel result={r} runId="run-1" />
    </QueryClientProvider>,
  );
}

describe("MlMetricsPanel", () => {
  it("renders nothing for a non-ML node", () => {
    const { container } = renderPanel(result({ type: "dropNulls" }));
    expect(container).toBeEmptyDOMElement();
  });

  it("shows metrics, task type, CV folds, and a register button for a trained model", () => {
    renderPanel(
      result({
        task_type: "classification",
        ml_metrics: { train_accuracy: 0.95, cm_true0_pred0: 3, cm_true1_pred1: 4 },
        cv_scores: [0.8, 0.9],
        model_uri: "models:/m-abc/1",
        mlflow_run_id: "abcdef123456",
      }),
    );
    expect(screen.getByText("Train accuracy")).toBeInTheDocument();
    expect(screen.getByText("classification")).toBeInTheDocument();
    expect(screen.getByText(/CV folds/i)).toBeInTheDocument();
    expect(screen.getByText("Confusion matrix")).toBeInTheDocument();
    expect(screen.getByText("models:/m-abc/1")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Register in registry/i })).toBeInTheDocument();
  });

  it("renders a feature-importance chart from the node sample", () => {
    renderPanel(
      result({
        type: "featureImportance",
        columns: ["feature_name", "importance", "rank"],
        sample: [
          { feature_name: "tenure", importance: 0.6, rank: 1 },
          { feature_name: "charges", importance: 0.4, rank: 2 },
        ],
      }),
    );
    expect(screen.getByText("Feature importance")).toBeInTheDocument();
    expect(screen.getByText("tenure")).toBeInTheDocument();
    expect(screen.getByText("charges")).toBeInTheDocument();
  });
});
