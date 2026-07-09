import { toast } from "@/stores/toastStore";
import { useFlowEditorStore } from "@/stores/flowEditorStore";

/**
 * Fire a success toast with an "Undo" action wired to the editor's single
 * global undo stack. Captures `sessionId` (bumped only by the store's
 * `reset()` — once per flow the user navigates away from, see
 * FlowEditorPage's flow-id effect cleanup) at creation time, and the callback
 * re-checks it before calling `undo()`. Without that check, a toast left over
 * from a flow the user has since switched away from could reach back and
 * undo an edit in the *new* flow — `undo()` itself has no notion of which
 * flow a history entry belongs to, only `reset()` draws that boundary.
 */
export function undoableToast(title: string): void {
  const sessionId = useFlowEditorStore.getState().sessionId;
  toast.success(title, {
    action: {
      label: "Undo",
      onClick: () => {
        if (useFlowEditorStore.getState().sessionId === sessionId) {
          useFlowEditorStore.getState().undo();
        }
      },
    },
  });
}
