import { Lightbulb } from "lucide-react";
import { getNodeDoc } from "@/lib/nodeDocs";

/** Renders the "Guide" tab content for a node: what it does, its fields,
 *  an example, and tips. Falls back gracefully when a type has no doc. */
export function NodeGuide({ type }: { type: string }) {
  const doc = getNodeDoc(type);
  if (!doc) {
    return (
      <p className="text-xs text-muted-foreground">
        No documentation available for this node yet.
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-3 text-xs leading-relaxed">
      <p className="text-slate-700">{doc.summary}</p>

      {doc.fields && doc.fields.length > 0 && (
        <div className="flex flex-col gap-2">
          <h3 className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
            Settings
          </h3>
          <dl className="flex flex-col gap-1.5">
            {doc.fields.map((f) => (
              <div key={f.name}>
                <dt className="font-medium text-slate-700">{f.name}</dt>
                <dd className="text-muted-foreground">{f.desc}</dd>
              </div>
            ))}
          </dl>
        </div>
      )}

      {doc.example && (
        <div className="rounded-md border border-border bg-muted/40 px-3 py-2">
          <div className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
            Example
          </div>
          <code className="text-[11px] text-slate-700">{doc.example}</code>
        </div>
      )}

      {doc.tips && doc.tips.length > 0 && (
        <ul className="flex flex-col gap-1.5">
          {doc.tips.map((tip, i) => (
            <li key={i} className="flex gap-1.5 text-muted-foreground">
              <Lightbulb className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-500" />
              <span>{tip}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
