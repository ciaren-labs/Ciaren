import { useMemo, useState } from "react";
import { AlertTriangle, FolderOpen, Trash2, X } from "lucide-react";
import { useFlowEditorStore } from "@/stores/flowEditorStore";
import { useDatasets } from "@/features/datasets/hooks";
import { getNodeTypeDef } from "@/lib/nodeCatalog";
import { CATEGORY_THEME, getNodeIcon } from "@/lib/nodeVisuals";
import { computeNodeColumns } from "@/lib/flowGraph";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { NodeConfigForm } from "./NodeConfigForm";
import { NodeGuide } from "./NodeGuide";

/**
 * Right-hand sidebar that edits the selected node's label and config. Writes
 * directly into the zustand editor store as the user types.
 */
export function NodeSidebar() {
  const selectedNodeId = useFlowEditorStore((s) => s.selectedNodeId);
  const nodes = useFlowEditorStore((s) => s.nodes);
  const edges = useFlowEditorStore((s) => s.edges);
  const updateNodeConfig = useFlowEditorStore((s) => s.updateNodeConfig);
  const updateNodeLabel = useFlowEditorStore((s) => s.updateNodeLabel);
  const removeNode = useFlowEditorStore((s) => s.removeNode);
  const selectNode = useFlowEditorStore((s) => s.selectNode);
  const flowProjectId = useFlowEditorStore((s) => s.flowProjectId);
  const { data: datasets } = useDatasets(flowProjectId ?? undefined);
  const [hasErrors, setHasErrors] = useState(false);

  // Columns available on the wire into the selected node, derived from the
  // upstream input datasets' schemas (recomputed as the graph changes).
  const columnsByNode = useMemo(
    () => computeNodeColumns(nodes, edges, datasets ?? []),
    [nodes, edges, datasets],
  );

  const node = nodes.find((n) => n.id === selectedNodeId);
  if (!node) {
    return (
      <div className="flex h-full w-80 items-center justify-center border-l border-border bg-muted/20 p-6 text-center text-sm text-muted-foreground">
        Select a node on the canvas to configure it.
      </div>
    );
  }

  const def = getNodeTypeDef(node.type ?? "");
  const theme = CATEGORY_THEME[def?.category ?? "clean"];
  const Icon = getNodeIcon(node.type);
  const columns = columnsByNode.get(node.id)?.input ?? [];

  return (
    <div className="flex h-full w-80 animate-slide-in-right flex-col gap-4 overflow-y-auto border-l border-border bg-background p-4">
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-2.5">
          <span className={cn("flex h-9 w-9 items-center justify-center rounded-lg shadow-sm", theme.badge)}>
            <Icon className="h-5 w-5" strokeWidth={2.25} />
          </span>
          <div>
            <h2 className="text-sm font-semibold leading-tight">{def?.label ?? node.type}</h2>
            <p className={cn("text-[10px] font-medium uppercase tracking-wide", theme.text)}>
              {def?.category}
            </p>
          </div>
        </div>
        <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => selectNode(null)}>
          <X className="h-4 w-4" />
        </Button>
      </div>

      <Tabs defaultValue="configure" className="flex flex-col gap-3">
        <TabsList className="w-full">
          <TabsTrigger value="configure" className="flex-1">
            Configure
          </TabsTrigger>
          <TabsTrigger value="guide" className="flex-1">
            Guide
          </TabsTrigger>
        </TabsList>

        <TabsContent value="configure" className="mt-0 flex flex-col gap-3">
          <div className="flex flex-col gap-1.5">
            <Label>Label</Label>
            <Input value={node.data.label} onChange={(e) => updateNodeLabel(node.id, e.target.value)} />
          </div>

          <div className="h-px bg-border" />

          <div className="flex flex-col gap-3.5">
            <NodeConfigForm
              type={node.type ?? ""}
              config={node.data.config}
              datasets={datasets ?? []}
              columns={columns}
              onChange={(config) => updateNodeConfig(node.id, config)}
              onErrors={setHasErrors}
            />
          </div>

          {flowProjectId && (
            <p className="flex items-center gap-1.5 rounded-md bg-muted/60 px-2.5 py-1.5 text-[11px] text-muted-foreground">
              <FolderOpen className="h-3.5 w-3.5 shrink-0" />
              Showing datasets from this flow's project only.
            </p>
          )}

          {hasErrors && (
            <p className="flex items-center gap-1.5 rounded-md bg-destructive/10 px-2.5 py-1.5 text-[11px] font-medium text-destructive">
              <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
              Fix the highlighted fields before running.
            </p>
          )}
        </TabsContent>

        <TabsContent value="guide" className="mt-0">
          <NodeGuide type={node.type ?? ""} />
        </TabsContent>
      </Tabs>

      <div className="mt-auto pt-2">
        <Button variant="destructive" size="sm" className="w-full" onClick={() => removeNode(node.id)}>
          <Trash2 className="h-4 w-4" /> Delete node
        </Button>
      </div>
    </div>
  );
}
