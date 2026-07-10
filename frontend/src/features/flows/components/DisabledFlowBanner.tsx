import { Power } from "lucide-react";

export function DisabledFlowBanner({ onReEnable }: { onReEnable: () => void }) {
  return (
    <div className="flex items-center gap-2 border-b border-amber-200 bg-amber-50 px-4 py-2 text-sm text-amber-800">
      <Power className="h-4 w-4 shrink-0" />
      This flow is disabled — it is read-only and cannot be run. Click
      <button
        className="font-semibold underline underline-offset-2 hover:text-amber-900"
        onClick={onReEnable}
      >
        Re-enable
      </button>
      to restore it.
    </div>
  );
}
