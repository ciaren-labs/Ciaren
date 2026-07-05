import { describe, expect, it } from "vitest";
import {
  buildEdgeId,
  handleCompatibility,
  isCompatibleConnection,
  isDuplicateEdge,
  nodeHasNoCompatibleHandle,
  type PendingConnection,
} from "../connectionRules";
import { NODE_TYPE_MAP } from "../nodeCatalog";

const d = (type: string) => NODE_TYPE_MAP[type];

describe("isCompatibleConnection", () => {
  it("allows a plain data wire between transforms", () => {
    expect(isCompatibleConnection(d("fileInput"), "out", d("dropNulls"), "in")).toBe(true);
    expect(isCompatibleConnection(d("dropNulls"), "out", d("fileOutput"), "in")).toBe(true);
  });

  it("rejects an output node as a source and an input node as a target", () => {
    expect(isCompatibleConnection(d("fileOutput"), "out", d("dropNulls"), "in")).toBe(false);
    expect(isCompatibleConnection(d("dropNulls"), "out", d("fileInput"), "in")).toBe(false);
  });

  it("rejects undefined defs (unknown node types)", () => {
    expect(isCompatibleConnection(undefined, "out", d("dropNulls"), "in")).toBe(false);
    expect(isCompatibleConnection(d("dropNulls"), "out", undefined, "in")).toBe(false);
  });

  it("rejects a model output dropped onto a data input", () => {
    expect(isCompatibleConnection(d("mlTrainClassifier"), "model", d("dropNulls"), "in")).toBe(false);
    expect(isCompatibleConnection(d("mlTrainClassifier"), "model", d("fileOutput"), "in")).toBe(false);
  });

  it("rejects a dataframe dropped onto a model input", () => {
    expect(isCompatibleConnection(d("dropNulls"), "out", d("mlPredict"), "model")).toBe(false);
    expect(isCompatibleConnection(d("dropNulls"), "out", d("featureImportance"), "model")).toBe(false);
  });

  it("allows model output → model input", () => {
    expect(isCompatibleConnection(d("mlTrainClassifier"), "model", d("mlPredict"), "model")).toBe(true);
    expect(isCompatibleConnection(d("mlTrainRegressor"), "model", d("featureImportance"), "model")).toBe(true);
  });

  it("resolves a null source handle to the node's primary output", () => {
    // A model node's sole output IS the model wire, even when the edge omits
    // the handle (seeded/imported flows).
    expect(isCompatibleConnection(d("mlTrainClassifier"), null, d("mlPredict"), "model")).toBe(true);
    expect(isCompatibleConnection(d("mlTrainClassifier"), null, d("dropNulls"), "in")).toBe(false);
  });

  it("only lets unfitted model definitions feed cross-validate", () => {
    expect(isCompatibleConnection(d("mlClassifierModel"), "model", d("mlCrossValidate"), "model")).toBe(true);
    expect(isCompatibleConnection(d("mlRegressorModel"), "model", d("mlCrossValidate"), "model")).toBe(true);
    expect(isCompatibleConnection(d("mlTrainClassifier"), "model", d("mlCrossValidate"), "model")).toBe(false);
    // The data input of cross-validate stays open to any transform.
    expect(isCompatibleConnection(d("dropNulls"), "out", d("mlCrossValidate"), "in")).toBe(true);
  });

  it("rejects handles the node does not declare", () => {
    expect(isCompatibleConnection(d("dropNulls"), "bogus", d("fileOutput"), "in")).toBe(false);
    expect(isCompatibleConnection(d("dropNulls"), "out", d("join"), "bogus")).toBe(false);
    expect(isCompatibleConnection(d("trainTestSplit"), "train", d("dropNulls"), "in")).toBe(true);
    expect(isCompatibleConnection(d("trainTestSplit"), "validation", d("dropNulls"), "in")).toBe(false);
  });

  it("accepts optional input handles (mlPredict's model port)", () => {
    expect(isCompatibleConnection(d("mlClassifierModel"), "model", d("mlPredict"), "model")).toBe(true);
  });
});

describe("isDuplicateEdge", () => {
  const existing = [
    { source: "a", sourceHandle: "train", target: "b", targetHandle: "in" },
    { source: "c", sourceHandle: null, target: "b", targetHandle: "in" },
  ];

  it("detects an exact duplicate", () => {
    expect(
      isDuplicateEdge(existing, { source: "a", sourceHandle: "train", target: "b", targetHandle: "in" }),
    ).toBe(true);
  });

  it("treats distinct source handles as distinct edges (split → concat)", () => {
    expect(
      isDuplicateEdge(existing, { source: "a", sourceHandle: "test", target: "b", targetHandle: "in" }),
    ).toBe(false);
  });

  it("normalizes a null handle against the primary output handle", () => {
    expect(
      isDuplicateEdge(existing, { source: "c", sourceHandle: "out", target: "b", targetHandle: "in" }, "out"),
    ).toBe(true);
    // With a different primary (e.g. a model node), "out" is NOT the resolved twin.
    expect(
      isDuplicateEdge(existing, { source: "c", sourceHandle: "out", target: "b", targetHandle: "in" }, "model"),
    ).toBe(false);
  });

  it("treats distinct target handles as distinct edges", () => {
    expect(
      isDuplicateEdge(existing, { source: "a", sourceHandle: "train", target: "b", targetHandle: "left" }),
    ).toBe(false);
  });
});

describe("buildEdgeId", () => {
  it("gives a split node's two outputs to the same target distinct ids", () => {
    const train = buildEdgeId({ source: "s", sourceHandle: "train", target: "t", targetHandle: "in" });
    const test = buildEdgeId({ source: "s", sourceHandle: "test", target: "t", targetHandle: "in" });
    expect(train).not.toEqual(test);
  });
});

describe("handleCompatibility / nodeHasNoCompatibleHandle", () => {
  const fromFileInput: PendingConnection = {
    nodeId: "n1",
    handleId: "out",
    handleType: "source",
    nodeType: "fileInput",
  };
  const fromTrainModel: PendingConnection = {
    nodeId: "n2",
    handleId: "model",
    handleType: "source",
    nodeType: "mlTrainClassifier",
  };
  const fromPredictModelInput: PendingConnection = {
    nodeId: "n3",
    handleId: "model",
    handleType: "target",
    nodeType: "mlPredict",
  };

  it("is idle when no drag is active or on the origin node itself", () => {
    expect(handleCompatibility(null, undefined, "x", d("dropNulls"), "in", "target")).toBe("idle");
    expect(
      handleCompatibility(fromFileInput, d("fileInput"), "n1", d("fileInput"), "out", "source"),
    ).toBe("idle");
  });

  it("marks data inputs compatible and model inputs incompatible for a data drag", () => {
    expect(
      handleCompatibility(fromFileInput, d("fileInput"), "x", d("dropNulls"), "in", "target"),
    ).toBe("compatible");
    expect(
      handleCompatibility(fromFileInput, d("fileInput"), "x", d("mlPredict"), "model", "target"),
    ).toBe("incompatible");
    expect(
      handleCompatibility(fromFileInput, d("fileInput"), "x", d("mlPredict"), "in", "target"),
    ).toBe("compatible");
  });

  it("dims same-kind handles: another source can never complete a source drag", () => {
    expect(
      handleCompatibility(fromFileInput, d("fileInput"), "x", d("dropNulls"), "out", "source"),
    ).toBe("incompatible");
  });

  it("marks model inputs compatible for a model drag", () => {
    expect(
      handleCompatibility(fromTrainModel, d("mlTrainClassifier"), "x", d("mlPredict"), "model", "target"),
    ).toBe("compatible");
    expect(
      handleCompatibility(fromTrainModel, d("mlTrainClassifier"), "x", d("dropNulls"), "in", "target"),
    ).toBe("incompatible");
    // Cross-validate refuses fitted train nodes even on its model port.
    expect(
      handleCompatibility(fromTrainModel, d("mlTrainClassifier"), "x", d("mlCrossValidate"), "model", "target"),
    ).toBe("incompatible");
  });

  it("supports reverse drags (started from a target handle)", () => {
    expect(
      handleCompatibility(fromPredictModelInput, d("mlPredict"), "x", d("mlTrainClassifier"), "model", "source"),
    ).toBe("compatible");
    expect(
      handleCompatibility(fromPredictModelInput, d("mlPredict"), "x", d("fileInput"), "out", "source"),
    ).toBe("incompatible");
  });

  it("resolves a null pending handle to the origin's primary handle", () => {
    const fromTrainNullHandle: PendingConnection = {
      nodeId: "n2",
      handleId: null,
      handleType: "source",
      nodeType: "mlTrainClassifier",
    };
    expect(
      handleCompatibility(fromTrainNullHandle, d("mlTrainClassifier"), "x", d("mlPredict"), "model", "target"),
    ).toBe("compatible");
    expect(
      handleCompatibility(fromTrainNullHandle, d("mlTrainClassifier"), "x", d("dropNulls"), "in", "target"),
    ).toBe("incompatible");
  });

  it("never dims the origin node itself", () => {
    expect(
      nodeHasNoCompatibleHandle(fromFileInput, d("fileInput"), "n1", d("fileInput")),
    ).toBe(false);
    expect(
      nodeHasNoCompatibleHandle(fromTrainModel, d("mlTrainClassifier"), "n2", d("mlTrainClassifier")),
    ).toBe(false);
  });

  it("dims by output-handle compatibility on reverse drags", () => {
    // Dragging backwards from mlPredict's model input: only model outputs fit.
    expect(
      nodeHasNoCompatibleHandle(fromPredictModelInput, d("mlPredict"), "x", d("mlTrainClassifier")),
    ).toBe(false);
    expect(
      nodeHasNoCompatibleHandle(fromPredictModelInput, d("mlPredict"), "x", d("dropNulls")),
    ).toBe(true);
    expect(
      nodeHasNoCompatibleHandle(fromPredictModelInput, d("mlPredict"), "x", d("fileOutput")),
    ).toBe(true);
  });

  it("stays inert for unknown node types (plugin catalog not yet loaded)", () => {
    expect(
      handleCompatibility(fromFileInput, d("fileInput"), "x", undefined, "in", "target"),
    ).toBe("idle");
    expect(nodeHasNoCompatibleHandle(fromFileInput, d("fileInput"), "x", undefined)).toBe(false);
  });

  it("flags nodes with no compatible handle so the card can dim", () => {
    // Dragging a model wire: a plain transform offers nowhere to drop it.
    expect(nodeHasNoCompatibleHandle(fromTrainModel, d("mlTrainClassifier"), "x", d("dropNulls"))).toBe(true);
    expect(nodeHasNoCompatibleHandle(fromTrainModel, d("mlTrainClassifier"), "x", d("mlPredict"))).toBe(false);
    // Dragging data: an input node can't receive anything.
    expect(nodeHasNoCompatibleHandle(fromFileInput, d("fileInput"), "x", d("fileInput"))).toBe(true);
    expect(nodeHasNoCompatibleHandle(fromFileInput, d("fileInput"), "x", d("fileOutput"))).toBe(false);
    // No drag → nothing dims.
    expect(nodeHasNoCompatibleHandle(null, undefined, "x", d("dropNulls"))).toBe(false);
  });
});
