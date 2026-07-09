import { Copy, Pencil, Trash2 } from "lucide-react";

export interface NodeContextMenuProps {
  x: number;
  y: number;
  onEdit: () => void;
  onDuplicate: () => void;
  onDelete: () => void;
  onClose: () => void;
}

/**
 * Right-click context menu for a canvas node: the same edit/duplicate/delete
 * actions as the hover toolbar (see FlowNode), for users who reach for a
 * context menu instead. Purely presentational — FlowCanvas owns which node
 * it's open for and composes each callback with closing the menu.
 */
export function NodeContextMenu({ x, y, onEdit, onDuplicate, onDelete, onClose }: NodeContextMenuProps) {
  return (
    <>
      {/* click-away */}
      <div
        className="fixed inset-0 z-40"
        onClick={onClose}
        onContextMenu={(e) => {
          e.preventDefault();
          onClose();
        }}
      />
      <div
        className="fixed z-50 w-40 overflow-hidden rounded-lg border border-border bg-background py-1 shadow-md"
        style={{ left: x, top: y }}
      >
        <button
          onClick={onEdit}
          className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-xs hover:bg-accent"
        >
          <Pencil className="h-3.5 w-3.5" /> Edit
        </button>
        <button
          onClick={onDuplicate}
          className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-xs hover:bg-accent"
        >
          <Copy className="h-3.5 w-3.5" /> Duplicate
        </button>
        <button
          onClick={onDelete}
          className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-xs text-destructive hover:bg-destructive/10"
        >
          <Trash2 className="h-3.5 w-3.5" /> Delete
        </button>
      </div>
    </>
  );
}
