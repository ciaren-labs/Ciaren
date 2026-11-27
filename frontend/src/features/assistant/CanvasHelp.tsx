import { useState } from "react";
import { BookOpen, CircleAlert, ScanLine } from "lucide-react";
import { Button } from "@/components/ui/button";
import { NODE_DOCS } from "@/features/flows/editor/nodeDocs";
import type { FlowValidation } from "@/features/flows/editor/flowValidation";
import { useFlowEditorStore } from "@/stores/flowEditorStore";

const guide =
  "https://github.com/ciaren-labs/Ciaren/blob/585e5b29f4793cc5878c1f53dce5baf0c8b61ed4/frontend/src/features/flows/editor/nodeDocs.ts";
export function CanvasHelp({
  validation,
  inspectNode,
}: {
  validation: FlowValidation;
  inspectNode: (id: string) => void;
}) {
  const selected = useFlowEditorStore((s) =>
    s.nodes.find((n) => n.id === s.selectedNodeId),
  );
  const empty = useFlowEditorStore((s) => s.nodes.length === 0);
  const [tool, setTool] = useState<"guide" | "check">();
  const doc =
    selected &&
    Object.prototype.hasOwnProperty.call(NODE_DOCS, selected.type ?? "")
      ? NODE_DOCS[selected.type!]
      : undefined;
  return (
    <section
      aria-label="Canvas tools"
      className="grid gap-2 border-t border-border pt-3"
    >
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold">
          {empty
            ? "Empty canvas"
            : selected
              ? selected.data.label
              : "On this canvas"}
        </h3>
        <span className="text-xs text-muted-foreground">On device</span>
      </div>
      <div className="flex flex-wrap gap-2">
        {doc && (
          <Button
            variant="outline"
            size="sm"
            aria-expanded={tool === "guide"}
            onClick={() => setTool(tool === "guide" ? undefined : "guide")}
          >
            <BookOpen aria-hidden className="size-4" />
            Explain selected node
          </Button>
        )}
        <Button
          variant="outline"
          size="sm"
          aria-expanded={tool === "check"}
          onClick={() => setTool(tool === "check" ? undefined : "check")}
        >
          <ScanLine aria-hidden className="size-4" />
          Check canvas
        </Button>
      </div>
      {tool === "guide" && doc && (
        <div
          role="status"
          className="space-y-2 border-t border-border pt-2 text-sm"
        >
          <p>{doc.summary}</p>
          {doc.tips?.[0] && <p>{doc.tips[0]}</p>}
          <a
            className="font-medium underline"
            href={guide}
            target="_blank"
            rel="noreferrer"
          >
            Ciaren node guide
          </a>
        </div>
      )}
      {tool === "check" && (
        <div
          role="status"
          className="grid gap-2 border-t border-border pt-2 text-sm"
        >
          {validation.issues.length === 0 ? (
            <p>
              Canvas checks passed. You can review the flow before running it.
            </p>
          ) : (
            validation.issues.slice(0, 5).map((issue, i) => (
              <div className="flex items-start gap-2" key={i}>
                <CircleAlert
                  aria-hidden
                  className="mt-0.5 size-4 shrink-0 text-muted-foreground"
                />
                <div>
                  <p>{issue.message}</p>
                  {issue.nodeId && (
                    <button
                      className="font-medium text-primary underline"
                      onClick={() => inspectNode(issue.nodeId!)}
                    >
                      Inspect node
                    </button>
                  )}
                </div>
              </div>
            ))
          )}
          {validation.issues.length > 5 && (
            <p>
              See the toolbar validation summary for all{" "}
              {validation.issues.length} issues.
            </p>
          )}
        </div>
      )}
    </section>
  );
}
