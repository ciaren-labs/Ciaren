import { useState } from "react";
import { useFlowEditorStore } from "@/stores/flowEditorStore";
import { useDatasets } from "@/features/datasets/hooks";
import { getNodeTypeDef } from "@/lib/nodeCatalog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { NodeConfigForm } from "./NodeConfigForm";

/**
 * Right-hand sidebar that edits the selected node's label and config. Writes
 * directly into the zustand editor store as the user types.
 */
export function NodeSidebar() {
  const selectedNodeId = useFlowEditorStore((s) => s.selectedNodeId);
  const nodes = useFlowEditorStore((s) => s.nodes);
  const updateNodeConfig = useFlowEditorStore((s) => s.updateNodeConfig);
  const updateNodeLabel = useFlowEditorStore((s) => s.updateNodeLabel);
  const removeNode = useFlowEditorStore((s) => s.removeNode);
  const selectNode = useFlowEditorStore((s) => s.selectNode);
  const { data: datasets } = useDatasets();
  const [hasErrors, setHasErrors] = useState(false);

  const node = nodes.find((n) => n.id === selectedNodeId);
  if (!node) {
    return (
      <div className="flex h-full w-72 items-center justify-center border-l border-border bg-muted/30 p-4 text-center text-sm text-muted-foreground">
        Select a node to configure it.
      </div>
    );
  }

  const def = getNodeTypeDef(node.type ?? "");

  return (
    <div className="flex h-full w-72 flex-col gap-3 overflow-y-auto border-l border-border bg-background p-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold">Node Config</h2>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => selectNode(null)}
        >
          Close
        </Button>
      </div>

      <div className="text-xs text-muted-foreground">{def?.description}</div>

      <div className="flex flex-col gap-1">
        <Label>Label</Label>
        <Input
          value={node.data.label}
          onChange={(e) => updateNodeLabel(node.id, e.target.value)}
        />
      </div>

      <div className="flex flex-col gap-3">
        <NodeConfigForm
          type={node.type ?? ""}
          config={node.data.config}
          datasets={datasets ?? []}
          onChange={(config) => updateNodeConfig(node.id, config)}
          onErrors={setHasErrors}
        />
      </div>

      {hasErrors && (
        <p className="text-[11px] text-destructive">
          Some fields are invalid. Fix them before running the flow.
        </p>
      )}

      <div className="mt-auto pt-2">
        <Button
          variant="destructive"
          size="sm"
          className="w-full"
          onClick={() => removeNode(node.id)}
        >
          Delete node
        </Button>
      </div>
    </div>
  );
}
