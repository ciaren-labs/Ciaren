import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { Dataset } from "@/features/datasets/types";
import type { GraphNode } from "@/features/flows/types";
import { ProposalReview } from "../ProposalReview";

const node = (
  id: string,
  type: string,
  label: string,
  config: Record<string, unknown>,
) =>
  ({
    id,
    type,
    position: { x: 0, y: 0 },
    data: { label, config },
  }) as GraphNode;

describe("ProposalReview", () => {
  it("describes every proposed node in words, never as raw settings", () => {
    const added = [
      node("in", "fileInput", "File Input", {
        dataset_id: "d1",
        dataset_version: null,
      }),
      node("calc", "calculatedColumn", "Calculated Column", {
        column_name: "revenue",
        expression: "price * qty",
      }),
      node("big", "filterExpression", "Filter by Expression", {
        expression: "revenue > 100",
      }),
      node("enc", "encodeCategories", "Encode Categories", {
        columns: ["contract"],
      }),
      node("cv", "mlCrossValidate", "Cross Validate", { n_splits: 5 }),
    ];
    render(
      <ProposalReview
        delta={{ added, changed: [], connected: [], disconnected: [] }}
        base={{ nodes: [], edges: [] }}
        datasets={[{ id: "d1", name: "orders.csv" } as Dataset]}
        inspectNode={() => {}}
        compact={false}
      />,
    );
    const list = screen.getByRole("list");
    expect(list.textContent).not.toMatch(/[{}]|null|undefined/);
    // Expressions are shown in full so they can be read before saving.
    expect(list.textContent).toContain("revenue = price * qty");
    expect(list.textContent).toContain("Keep rows where revenue > 100");
    expect(list.textContent).toContain("orders.csv");
  });
});
