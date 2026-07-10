import { useEffect, useState } from "react";
import { Check, Info, Loader2, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { ErrorState, LoadingState } from "@/components/ui/PageState";
import { cn } from "@/lib/utils";
import type { AppSetting } from "@/features/settings/types";
import { useAppSettings, useResetAppSetting, useUpdateAppSetting } from "./hooks";

/** Group while preserving the backend's ordering (categories and items). */
function groupByCategory(settings: AppSetting[]): [string, AppSetting[]][] {
  const groups = new Map<string, AppSetting[]>();
  for (const s of settings) {
    const list = groups.get(s.category) ?? [];
    list.push(s);
    groups.set(s.category, list);
  }
  return [...groups.entries()];
}

function SourceBadge({ setting }: { setting: AppSetting }) {
  if (setting.source === "override") {
    return (
      <span className="rounded-full border border-brand-300 bg-brand-50 px-2 py-0.5 text-[11px] font-medium text-brand-700 dark:border-brand-700 dark:bg-brand-900/40 dark:text-brand-300">
        Custom
      </span>
    );
  }
  if (setting.source === "env") {
    return (
      <span className="rounded-full border border-border bg-muted px-2 py-0.5 text-[11px] font-medium text-muted-foreground">
        From environment
      </span>
    );
  }
  return null;
}

/** Client-side mirror of the backend's validation, for instant feedback only —
 * the server re-validates every write. */
function validateDraft(setting: AppSetting, draft: string): string | null {
  if (setting.value_type === "integer") {
    if (!/^-?\d+$/.test(draft.trim())) return "Enter a whole number.";
    const n = Number(draft);
    if (setting.min_value !== null && n < setting.min_value) return `Must be at least ${setting.min_value}.`;
    if (setting.max_value !== null && n > setting.max_value) return `Must be at most ${setting.max_value}.`;
  }
  if (setting.value_type === "url" && draft.trim() !== "" && !/^https?:\/\/.+/.test(draft.trim())) {
    return "Must be an http:// or https:// URL, or empty to disable.";
  }
  return null;
}

function SettingRow({ setting }: { setting: AppSetting }) {
  const update = useUpdateAppSetting();
  const reset = useResetAppSetting();
  const [draft, setDraft] = useState(String(setting.value));

  // Sync the draft when the server value changes (save, reset, refetch).
  useEffect(() => {
    setDraft(String(setting.value));
  }, [setting.value]);

  const dirty = draft !== String(setting.value);
  const problem = dirty ? validateDraft(setting, draft) : null;
  const busy = update.isPending || reset.isPending;

  const save = () => {
    if (!dirty || problem) return;
    const value = setting.value_type === "integer" ? Number(draft) : draft.trim();
    update.mutate({ key: setting.key, value });
  };

  return (
    <div className="flex flex-col gap-3 p-4 sm:flex-row sm:items-start sm:justify-between">
      <div className="min-w-0 sm:max-w-[55%]">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="text-sm font-medium">{setting.label}</h3>
          <SourceBadge setting={setting} />
        </div>
        <p className="mt-1 text-xs text-muted-foreground">{setting.description}</p>
        <p className="mt-1 font-mono text-[11px] text-muted-foreground/70">{setting.env_var}</p>
        {setting.source === "override" && (
          <p className="mt-1 flex items-center gap-1 text-[11px] text-sky-600 dark:text-sky-400">
            <Info className="h-3 w-3 shrink-0" />
            Set from this page — changes to {setting.env_var} are ignored until you press Reset.
          </p>
        )}
        {setting.restart_required && (
          <p className="mt-1 flex items-center gap-1 text-[11px] text-amber-600 dark:text-amber-400">
            <Info className="h-3 w-3 shrink-0" /> Takes full effect after the server restarts.
          </p>
        )}
        {problem && (
          <p role="alert" className="mt-1 text-xs text-destructive">
            {problem}
          </p>
        )}
      </div>

      <div className="flex shrink-0 items-center gap-2">
        {setting.value_type === "select" ? (
          <Select
            aria-label={`setting-${setting.key}`}
            className="w-40"
            value={draft}
            disabled={busy}
            onChange={(e) => setDraft(e.target.value)}
          >
            {(setting.choices ?? []).map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </Select>
        ) : (
          <Input
            aria-label={`setting-${setting.key}`}
            className={cn(setting.value_type === "url" ? "w-72" : "w-32", problem && "border-destructive")}
            type={setting.value_type === "integer" ? "number" : "text"}
            min={setting.min_value ?? undefined}
            max={setting.max_value ?? undefined}
            placeholder={setting.value_type === "url" ? "https://…" : undefined}
            value={draft}
            disabled={busy}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") save();
              if (e.key === "Escape") setDraft(String(setting.value));
            }}
          />
        )}

        {dirty && (
          <Button aria-label={`save-${setting.key}`} size="sm" disabled={busy || !!problem} onClick={save}>
            {update.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Check className="h-3.5 w-3.5" />}
            Save
          </Button>
        )}

        {setting.source === "override" && !dirty && (
          <Button
            aria-label={`reset-${setting.key}`}
            variant="outline"
            size="sm"
            disabled={busy}
            title={`Reset to ${String(setting.env_value) === "" ? "empty" : setting.env_value} (environment/default)`}
            onClick={() => reset.mutate(setting.key)}
          >
            {reset.isPending ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <RotateCcw className="h-3.5 w-3.5" />
            )}
            Reset
          </Button>
        )}
      </div>
    </div>
  );
}

export function SettingsPage() {
  const { data: settings, isPending, isError, error, refetch } = useAppSettings();

  return (
    <div className="mx-auto max-w-4xl px-6 py-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold">Settings</h1>
        <p className="text-sm text-muted-foreground">
          Runtime configuration for this Ciaren server. Values start from the server&apos;s environment
          (or built-in defaults); anything you change here is saved in Ciaren&apos;s database, applies to
          everyone using this server, and survives restarts. Reset a setting to follow the environment again.
        </p>
      </div>

      {isPending ? (
        <LoadingState label="Loading settings…" />
      ) : isError ? (
        <ErrorState error={error} title="Couldn't load settings" onRetry={() => refetch()} />
      ) : (
        <div className="space-y-8">
          {groupByCategory(settings ?? []).map(([category, items]) => (
            <section key={category} aria-label={category}>
              <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                {category}
              </h2>
              <div className="divide-y divide-border rounded-xl border border-border bg-card">
                {items.map((s) => (
                  <SettingRow key={s.key} setting={s} />
                ))}
              </div>
            </section>
          ))}

          <p className="text-xs text-muted-foreground">
            Deployment-level configuration — database, data directory, authentication tokens, CORS, and
            the security guards — can only be set through environment variables on the server. See the
            docs under <span className="font-medium">Guide → Advanced setup</span>.
          </p>
        </div>
      )}
    </div>
  );
}
