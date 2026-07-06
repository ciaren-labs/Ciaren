import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, FolderOpen, Trash2, X } from "lucide-react";
import { useFlowEditorStore } from "@/stores/flowEditorStore";
import { useDatasets } from "@/features/datasets/hooks";
import { getNodeTypeDef } from "@/lib/nodeCatalog";
import { getCategoryTheme, getNodeIcon } from "@/lib/nodeVisuals";
import { cleanStaleColumnRefs, computeNodeColumns, getDownstreamNodeIds, isInputType } from "@/lib/flowGraph";
import { referencedParameters, riskyParameterRefs } from "@/lib/parameters";
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
  const patchMultipleNodeConfigs = useFlowEditorStore((s) => s.patchMultipleNodeConfigs);
  const updateNodeLabel = useFlowEditorStore((s) => s.updateNodeLabel);
  const removeNode = useFlowEditorStore((s) => s.removeNode);
  const selectNode = useFlowEditorStore((s) => s.selectNode);
  const flowProjectId = useFlowEditorStore((s) => s.flowProjectId);
  const parameters = useFlowEditorStore((s) => s.parameters);
  const { data: datasets } = useDatasets(flowProjectId ?? undefined);
  const [hasErrors, setHasErrors] = useState(false);
  const [schemaWarning, setSchemaWarning] = useState(0);

  // Reset warning whenever the user switches to a different node.
  useEffect(() => { setSchemaWarning(0); }, [selectedNodeId]);

  // Columns available on the wire into the selected node, derived from the
  // upstream input datasets' schemas. Keyed on structureVersion, not `nodes`:
  // column propagation doesn't depend on node positions, and `nodes` is
  // replaced on every drag frame.
  const structureVersion = useFlowEditorStore((s) => s.structureVersion);
  const columnsByNode = useMemo(
    () => computeNodeColumns(nodes, edges, datasets ?? []),
    // eslint-disable-next-line react-hooks/exhaustive-deps -- structureVersion tracks nodes/edges structurally
    [structureVersion, datasets],
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
  // getCategoryTheme falls back to a neutral theme for plugin-contributed
  // categories that aren't built in (direct indexing would be undefined → crash).
  const theme = getCategoryTheme(def?.category ?? "clean");
  const Icon = getNodeIcon(node.type);
  const columns = columnsByNode.get(node.id)?.input ?? [];

  // Flow parameters the user can drop into config fields with {{ name }}, plus
  // any reference in this node's config that doesn't match a declared parameter.
  const paramNames = new Set(parameters.map((p) => p.name));
  const unknownRefs = [...referencedParameters(node.data.config)].filter((r) => !paramNames.has(r));
  // Parameters referenced inside a field this node type executes as code/query
  // text (pythonTransform script, eval expression, raw SQL) rather than an
  // inert value — a run-time override here can change logic, not just a value.
  const riskyRefs = riskyParameterRefs(node.type ?? "", node.data.config);

  const handleConfigChange = (newConfig: Record<string, unknown>) => {
    // When a file-input node's dataset changes, scan downstream nodes for
    // column references that no longer resolve and clear them. Each node is
    // checked against its OWN propagated input columns (rename/calculated
    // columns upstream, both sides of a join), not the raw dataset schema —
    // validating against the schema wiped perfectly valid references to
    // derived columns and to the join's other, unchanged branch.
    if (isInputType(node.type)) {
      const oldId = node.data.config.dataset_id;
      const newId = newConfig.dataset_id;
      if (oldId !== newId && typeof newId === "string" && newId) {
        const ds = (datasets ?? []).find((d) => d.id === newId);
        if (ds?.column_schema?.length) {
          const nodesWithNewConfig = nodes.map((n) =>
            n.id === node.id ? { ...n, data: { ...n.data, config: newConfig } } : n,
          );
          const colsByNode = computeNodeColumns(nodesWithNewConfig, edges, datasets ?? []);
          const downstream = getDownstreamNodeIds(node.id, edges);
          const patches: Record<string, Record<string, unknown>> = { [node.id]: newConfig };
          let staleCount = 0;
          for (const did of downstream) {
            const dn = nodes.find((n) => n.id === did);
            if (!dn) continue;
            const inputCols = colsByNode.get(did)?.input ?? [];
            // No schema information for this node's inputs (e.g. an unprofiled
            // dataset on another branch): leave its config alone rather than
            // wiping references we can't actually check.
            if (!inputCols.length) continue;
            const { patched, hadStale } = cleanStaleColumnRefs(
              dn.type ?? "",
              dn.data.config,
              new Set(inputCols),
            );
            if (hadStale) { patches[did] = patched; staleCount++; }
          }
          patchMultipleNodeConfigs(patches);
          setSchemaWarning(staleCount);
          return;
        }
      }
    }
    updateNodeConfig(node.id, newConfig);
    if (schemaWarning > 0) setSchemaWarning(0);
  };

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
              projectId={flowProjectId}
              columns={columns}
              onChange={handleConfigChange}
              onErrors={setHasErrors}
            />
          </div>

          {parameters.length > 0 && (
            <div className="rounded-md bg-muted/50 px-2.5 py-2 text-[11px] text-muted-foreground">
              <span className="font-medium text-foreground">Flow parameters</span> — insert into any
              field with <code className="rounded bg-background px-1">{"{{ name }}"}</code>:
              <div className="mt-1 flex flex-wrap gap-1">
                {parameters.map((p) => (
                  <code
                    key={p.name}
                    className="rounded border border-border bg-background px-1 py-0.5"
                    title={`${p.type}${p.description ? ` — ${p.description}` : ""}`}
                  >
                    {`{{ ${p.name} }}`}
                  </code>
                ))}
              </div>
            </div>
          )}

          {riskyRefs.size > 0 && (
            <p className="flex items-start gap-1.5 rounded-md border border-destructive/30 bg-destructive/5 px-2.5 py-2 text-[11px] text-destructive">
              <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              <span>
                This field runs as code/query text —{" "}
                <span className="font-medium">{[...riskyRefs].join(", ")}</span>{" "}
                {riskyRefs.size > 1 ? "are substituted" : "is substituted"} literally, not passed as a
                bound value. Only accept run-time overrides here from callers as trusted as this flow's
                author.
              </span>
            </p>
          )}

          {unknownRefs.length > 0 && (
            <p className="flex items-start gap-1.5 rounded-md border border-amber-200 bg-amber-50 px-2.5 py-2 text-[11px] text-amber-700">
              <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              <span>
                References unknown parameter{unknownRefs.length > 1 ? "s" : ""}{" "}
                <span className="font-medium">{unknownRefs.join(", ")}</span> — declare{" "}
                {unknownRefs.length > 1 ? "them" : "it"} in Parameters, or fix the reference.
              </span>
            </p>
          )}

          {schemaWarning > 0 && (
            <div className="flex items-start gap-1.5 rounded-md bg-amber-50 px-2.5 py-2 text-[11px] text-amber-700 border border-amber-200">
              <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              <span className="flex-1">
                Column settings in {schemaWarning}{" "}
                {schemaWarning === 1 ? "downstream node were" : "downstream nodes were"} reset — the
                new dataset has a different schema.
              </span>
              <button
                type="button"
                className="shrink-0 text-amber-600 hover:text-amber-800"
                onClick={() => setSchemaWarning(0)}
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
          )}

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
