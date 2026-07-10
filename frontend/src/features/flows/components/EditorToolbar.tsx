import {
  ArrowLeft,
  CalendarClock,
  Code2,
  Eye,
  EyeOff,
  Loader2,
  Pencil,
  Play,
  Power,
  Redo2,
  Save,
  Undo2,
  Variable,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { KeyboardShortcutsHelp } from "@/components/flow/KeyboardShortcutsHelp";
import { ValidationSummary } from "@/components/flow/ValidationSummary";
import type { FlowValidation } from "@/lib/flowValidation";
import { GatedButton } from "./GatedButton";

export function EditorToolbar({
  flowName,
  onBack,
  onRename,
  projectName,
  isDisabled,
  dirty,
  validation,
  onReEnable,
  toggleFlowPending,
  canUndo,
  canRedo,
  onUndo,
  onRedo,
  previewOpen,
  onTogglePreview,
  previewReason,
  engine,
  onEngineChange,
  canRun,
  createRunPending,
  runReason,
  onRun,
  canExport,
  onExport,
  parametersCount,
  onOpenParameters,
  onOpenSchedule,
  onSave,
  savePending,
}: {
  flowName: string;
  onBack: () => void;
  onRename: () => void;
  projectName: string | null;
  isDisabled: boolean;
  dirty: boolean;
  validation: FlowValidation;
  onReEnable: () => void;
  toggleFlowPending: boolean;
  canUndo: boolean;
  canRedo: boolean;
  onUndo: () => void;
  onRedo: () => void;
  previewOpen: boolean;
  onTogglePreview: () => void;
  previewReason?: string;
  engine: "pandas" | "polars";
  onEngineChange: (engine: "pandas" | "polars") => void;
  canRun: boolean;
  createRunPending: boolean;
  runReason?: string;
  onRun: () => void;
  canExport: boolean;
  onExport: () => void;
  parametersCount: number;
  onOpenParameters: () => void;
  onOpenSchedule: () => void;
  onSave: () => void;
  savePending: boolean;
}) {
  return (
    <div className="flex items-center justify-between border-b border-border bg-background/80 px-4 py-2 backdrop-blur">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="sm" onClick={onBack}>
          <ArrowLeft className="h-4 w-4" /> Flows
        </Button>
        <h1 className="text-sm font-semibold">{flowName}</h1>
        <button
          onClick={onRename}
          className="rounded-md p-1 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          title="Rename flow"
        >
          <Pencil className="h-3.5 w-3.5" />
        </button>
        {projectName && (
          <span className="text-xs text-muted-foreground">
            / {projectName}
          </span>
        )}
        {isDisabled && (
          <span className="rounded-md bg-muted px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground">
            disabled
          </span>
        )}
        {!isDisabled && dirty && (
          <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[11px] font-medium text-amber-700">
            unsaved
          </span>
        )}
        {!isDisabled && <ValidationSummary validation={validation} />}
      </div>
      <div className="flex items-center gap-2">
        {isDisabled ? (
          <Button
            size="sm"
            variant="outline"
            onClick={onReEnable}
            disabled={toggleFlowPending}
          >
            <Power className="h-4 w-4" /> Re-enable flow
          </Button>
        ) : (
          <>
            <div className="flex items-center overflow-hidden rounded-md border border-input">
              <Tooltip>
                <TooltipTrigger asChild>
                  <span>
                    <Button
                      size="sm"
                      variant="ghost"
                      className="rounded-none border-0 border-r border-input"
                      disabled={!canUndo}
                      onClick={onUndo}
                      aria-label="Undo"
                    >
                      <Undo2 className="h-4 w-4" />
                    </Button>
                  </span>
                </TooltipTrigger>
                <TooltipContent>Undo (Ctrl+Z)</TooltipContent>
              </Tooltip>
              <Tooltip>
                <TooltipTrigger asChild>
                  <span>
                    <Button
                      size="sm"
                      variant="ghost"
                      className="rounded-none border-0"
                      disabled={!canRedo}
                      onClick={onRedo}
                      aria-label="Redo"
                    >
                      <Redo2 className="h-4 w-4" />
                    </Button>
                  </span>
                </TooltipTrigger>
                <TooltipContent>Redo (Ctrl+Y)</TooltipContent>
              </Tooltip>
            </div>
            <KeyboardShortcutsHelp />
            <GatedButton
              disabled={!validation.canPreview}
              reason={previewReason}
              variant="outline"
              onClick={onTogglePreview}
            >
              {previewOpen ? (
                <EyeOff className="h-4 w-4" />
              ) : (
                <Eye className="h-4 w-4" />
              )}
              {previewOpen ? "Hide preview" : "Preview"}
            </GatedButton>
            <div className="flex items-center overflow-hidden rounded-md border border-input">
              <select
                value={engine}
                onChange={(e) => onEngineChange(e.target.value as "pandas" | "polars")}
                title="Execution engine"
                className="h-9 border-r border-input bg-background px-2 text-xs font-medium focus-visible:outline-none"
              >
                <option value="pandas">pandas</option>
                <option value="polars">polars</option>
              </select>
              <GatedButton
                disabled={!canRun || createRunPending}
                reason={runReason}
                onClick={onRun}
                className="rounded-none border-0"
              >
                {createRunPending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Play className="h-4 w-4" />
                )}
                Run
              </GatedButton>
            </div>
            <GatedButton
              disabled={!canExport}
              reason={runReason}
              variant="outline"
              onClick={onExport}
            >
              <Code2 className="h-4 w-4" /> Export
            </GatedButton>
            <Button size="sm" variant="outline" onClick={onOpenParameters}>
              <Variable className="h-4 w-4" /> Parameters
              {parametersCount > 0 && (
                <span className="ml-1 rounded-full bg-brand-100 px-1.5 text-[10px] font-medium text-brand-700">
                  {parametersCount}
                </span>
              )}
            </Button>
            <Button size="sm" variant="outline" onClick={onOpenSchedule}>
              <CalendarClock className="h-4 w-4" /> Schedule
            </Button>
            <Button size="sm" onClick={onSave} disabled={savePending}>
              {savePending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Save className="h-4 w-4" />
              )}
              {savePending ? "Saving…" : "Save"}
            </Button>
          </>
        )}
      </div>
    </div>
  );
}
