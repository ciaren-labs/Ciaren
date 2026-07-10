// Flow-level validation: turns the current graph + datasets into a list of
// human-readable issues and a set of capability flags that gate the Run /
// Export / Preview actions. Pure and dependency-light so it is unit-tested
// directly and reused by the editor header and node sidebar.

import {
  canConnectModelToTarget,
  getNodeTypeDef,
  getOutputHandles,
  isModelInputHandle,
  isModelOutputHandle,
} from "./nodeCatalog";
import { getConfigSchema } from "@/lib/validators";
import {
  FILE_INPUT_FORMAT_TO_SOURCE,
  INPUT_SOURCE_TYPE,
  hasCycle,
  isInputType,
  type GraphEdgeLike,
  type GraphNodeLike,
} from "./flowGraph";
import type { Dataset } from "@/features/datasets/types";

export type IssueSeverity = "error" | "warning";

export interface FlowIssue {
  severity: IssueSeverity;
  message: string;
  /** Node the issue belongs to, when it is node-specific. */
  nodeId?: string;
  /** Stable code so the UI can treat certain issues specially. */
  code: string;
}

export interface FlowValidation {
  issues: FlowIssue[];
  errors: FlowIssue[];
  warnings: FlowIssue[];
  /** Issues keyed by node id (errors only) for inline badges. */
  errorsByNode: Map<string, FlowIssue[]>;
  /** True when the flow can be executed end-to-end (needs an output node). */
  canRun: boolean;
  /** Same requirements as run — export compiles the full graph. */
  canExport: boolean;
  /** Preview tolerates a missing output node, but not config/wiring errors. */
  canPreview: boolean;
}

function incomingCount(
  edges: GraphEdgeLike[],
  nodeId: string,
): Map<string, number> {
  const byHandle = new Map<string, number>();
  for (const e of edges) {
    if (e.target !== nodeId) continue;
    const handle = e.targetHandle ?? "in";
    byHandle.set(handle, (byHandle.get(handle) ?? 0) + 1);
  }
  return byHandle;
}

/**
 * Validate the whole flow. `datasets` is used to verify that input nodes point
 * at an existing dataset of the matching source type (e.g. an Excel Input node
 * may not reference a Parquet dataset).
 */
export function validateFlow(
  nodes: GraphNodeLike[],
  edges: GraphEdgeLike[],
  datasets: Dataset[],
): FlowValidation {
  const issues: FlowIssue[] = [];
  const datasetById = new Map(datasets.map((d) => [d.id, d]));
  const nodeById = new Map(nodes.map((n) => [n.id, n]));

  if (nodes.length === 0) {
    issues.push({
      severity: "error",
      code: "EMPTY",
      message: "The flow is empty. Add an input node to get started.",
    });
  }

  let outputCount = 0;

  for (const node of nodes) {
    const def = getNodeTypeDef(node.type ?? "");

    if (!def) {
      issues.push({
        severity: "error",
        code: "UNKNOWN_TYPE",
        nodeId: node.id,
        message: `Unknown node type "${node.type}".`,
      });
      continue;
    }

    // Output nodes (no downstream output), model sinks (mlTrain logs to MLflow),
    // and report nodes (cross-validation emits a scores frame) all count as a
    // valid flow terminal.
    if (!def.hasOutput || def.isModelSink || def.isFlowTerminal) outputCount += 1;

    // 1. Config shape (zod) -------------------------------------------------
    const parsed = getConfigSchema(node.type ?? "").safeParse(node.data.config);
    if (!parsed.success) {
      const first = parsed.error.issues[0]?.message ?? "Invalid configuration";
      issues.push({
        severity: "error",
        code: "CONFIG_INVALID",
        nodeId: node.id,
        message: `${def.label}: ${first}`,
      });
    }

    // 2. Input-node dataset compatibility ----------------------------------
    if (isInputType(node.type)) {
      const datasetId = node.data.config.dataset_id;
      const expected =
        node.type === "fileInput"
          ? FILE_INPUT_FORMAT_TO_SOURCE[String(node.data.config.format ?? "csv")] ?? "csv"
          : INPUT_SOURCE_TYPE[node.type!];
      if (typeof datasetId === "string" && datasetId) {
        const ds = datasetById.get(datasetId);
        if (!ds) {
          issues.push({
            severity: "error",
            code: "DATASET_MISSING",
            nodeId: node.id,
            message: `${def.label}: the selected dataset no longer exists.`,
          });
        } else if (ds.source_type !== expected) {
          issues.push({
            severity: "error",
            code: "DATASET_TYPE_MISMATCH",
            nodeId: node.id,
            message: `${def.label} expects a ${expected.toUpperCase()} dataset, but "${ds.name}" is ${ds.source_type.toUpperCase()}.`,
          });
        } else {
          // Version pin checks: a pin beyond the latest version is broken; a pin
          // behind the latest is a (non-blocking) drift warning.
          const pinned = node.data.config.dataset_version;
          if (typeof pinned === "number" && pinned > ds.latest_version) {
            issues.push({
              severity: "error",
              code: "VERSION_MISSING",
              nodeId: node.id,
              message: `${def.label}: pinned version v${pinned} of "${ds.name}" no longer exists (latest is v${ds.latest_version}).`,
            });
          } else if (typeof pinned === "number" && pinned < ds.latest_version) {
            issues.push({
              severity: "warning",
              code: "VERSION_OUTDATED",
              nodeId: node.id,
              message: `${def.label}: pinned to v${pinned} of "${ds.name}"; v${ds.latest_version} is available.`,
            });
          }
        }
      }
    } else {
      // 3. Required inputs are wired up -------------------------------------
      const counts = incomingCount(edges, node.id);
      if (def.multiInput) {
        const total = [...counts.values()].reduce((a, b) => a + b, 0);
        if (total === 0) {
          issues.push({
            severity: "error",
            code: "INPUT_MISSING",
            nodeId: node.id,
            message: `${def.label}: connect at least one input.`,
          });
        } else if (total < 2) {
          issues.push({
            severity: "warning",
            code: "INPUT_SPARSE",
            nodeId: node.id,
            message: `${def.label}: stacking is only meaningful with two or more inputs.`,
          });
        }
      } else {
        for (const handle of def.inputHandles) {
          if ((counts.get(handle) ?? 0) === 0) {
            const which = def.inputHandles.length > 1 ? ` "${handle}"` : "";
            issues.push({
              severity: "error",
              code: "INPUT_MISSING",
              nodeId: node.id,
              message: `${def.label}: the${which} input is not connected.`,
            });
          }
        }
        // More than one wire into a single-input handle can't happen through
        // the canvas, but an imported graph can carry it — and the backend
        // refuses to run it, so surface the error here too.
        for (const [handle, count] of counts) {
          if (count > 1) {
            const which =
              def.inputHandles.length + (def.optionalInputHandles?.length ?? 0) > 1
                ? ` "${handle}"`
                : "";
            issues.push({
              severity: "error",
              code: "INPUT_CONFLICT",
              nodeId: node.id,
              message: `${def.label}: the${which} input has ${count} connections but accepts only one. Remove the extra wires.`,
            });
          }
        }
      }

      // 3b. mlPredict needs a model: either the "model" input wired from an
      // mlTrain node, or a registered-model URI in its config. Without one it
      // has nothing to predict with.
      if (node.type === "mlPredict") {
        const hasModelWire = (counts.get("model") ?? 0) > 0;
        const modelUri = node.data.config.model_uri;
        const hasModelUri = typeof modelUri === "string" && modelUri.trim() !== "";
        if (!hasModelWire && !hasModelUri) {
          issues.push({
            severity: "error",
            code: "MODEL_MISSING",
            nodeId: node.id,
            message: `${def.label}: connect a model to the "model" input, or set a model URI in its config.`,
          });
        }
      }
    }
  }

  // 4. Model-wire compatibility --------------------------------------------
  // The canvas blocks these interactively, but a graph can also arrive with
  // its edges already in place (imported, migrated, hand-edited JSON), so the
  // same rules are re-checked here — mirroring the backend guard.
  for (const edge of edges) {
    const source = nodeById.get(edge.source);
    const target = nodeById.get(edge.target);
    const sourceDef = source ? getNodeTypeDef(source.type ?? "") : undefined;
    const targetDef = target ? getNodeTypeDef(target.type ?? "") : undefined;
    if (!sourceDef || !targetDef) continue;
    // A multi-output source (train/test split) must say which output the edge
    // leaves from; the backend rejects an ambiguous or unknown source handle.
    const outs = getOutputHandles(sourceDef);
    if (
      (outs.length > 1 && edge.sourceHandle == null) ||
      (edge.sourceHandle != null && !outs.includes(edge.sourceHandle))
    ) {
      issues.push({
        severity: "error",
        code: "SOURCE_HANDLE_INVALID",
        nodeId: edge.source,
        message:
          edge.sourceHandle == null
            ? `${sourceDef.label}: an outgoing connection must choose one of its outputs (${outs.join(", ")}).`
            : `${sourceDef.label}: an outgoing connection uses unknown output "${edge.sourceHandle}".`,
      });
      continue;
    }
    const carriesModel = isModelOutputHandle(sourceDef, edge.sourceHandle);
    const wantsModel = isModelInputHandle(targetDef, edge.targetHandle ?? "in");
    if (carriesModel && !wantsModel) {
      issues.push({
        severity: "error",
        code: "MODEL_WIRE_MISMATCH",
        nodeId: edge.target,
        message:
          `${targetDef.label}: the connection from ${sourceDef.label} carries a trained model, ` +
          `but this input expects data. Wire the model into a "model" input instead.`,
      });
      continue;
    }
    if (!carriesModel && wantsModel) {
      issues.push({
        severity: "error",
        code: "MODEL_WIRE_MISMATCH",
        nodeId: edge.target,
        message:
          `${targetDef.label}: the "model" input expects a trained model, ` +
          `but ${sourceDef.label} outputs data. Connect a train or model node instead.`,
      });
      continue;
    }
    if (carriesModel && wantsModel && !canConnectModelToTarget(sourceDef, targetDef)) {
      issues.push({
        severity: "error",
        code: "MODEL_SOURCE_MISMATCH",
        nodeId: edge.target,
        message:
          `${targetDef.label}: connect Classifier Model or Regressor Model to cross-validate. ` +
          "Train nodes fit a final model and would make cross-validation do extra work.",
      });
    }
  }

  // 5. Whole-graph checks ---------------------------------------------------
  if (nodes.length > 0 && outputCount === 0) {
    issues.push({
      severity: "error",
      code: "NO_OUTPUT",
      message: "Add an output node so the result can be written somewhere.",
    });
  }

  if (hasCycle(nodes, edges)) {
    issues.push({
      severity: "error",
      code: "CYCLE",
      message: "The flow has a cycle. Transformations must form a one-way pipeline.",
    });
  }

  // Orphan nodes (no edges at all, and not a lone input being configured).
  const connected = new Set<string>();
  for (const e of edges) {
    connected.add(e.source);
    connected.add(e.target);
  }
  if (nodes.length > 1) {
    for (const node of nodes) {
      if (!connected.has(node.id)) {
        const def = getNodeTypeDef(node.type ?? "");
        issues.push({
          severity: "warning",
          code: "ORPHAN",
          nodeId: node.id,
          message: `${def?.label ?? node.type} is not connected to anything.`,
        });
      }
    }
  }

  const errors = issues.filter((i) => i.severity === "error");
  const warnings = issues.filter((i) => i.severity === "warning");
  const errorsByNode = new Map<string, FlowIssue[]>();
  for (const e of errors) {
    if (!e.nodeId) continue;
    const list = errorsByNode.get(e.nodeId) ?? [];
    list.push(e);
    errorsByNode.set(e.nodeId, list);
  }

  const hardErrors = errors.length === 0;
  // Preview can run on a partial pipeline, so it ignores the "no output" error.
  const previewBlocking = errors.filter((e) => e.code !== "NO_OUTPUT");

  return {
    issues,
    errors,
    warnings,
    errorsByNode,
    canRun: hardErrors,
    canExport: hardErrors,
    canPreview: nodes.length > 0 && previewBlocking.length === 0,
  };
}
