import { useEffect, useId, useRef, useState } from "react";
import type { FormEvent, ReactNode } from "react";
import { KeyRound, Pencil, Plus, ShieldAlert, Trash2 } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { ErrorState, LoadingState } from "@/components/ui/PageState";
import { ApiError } from "@/lib/api/client";
import { keys, status } from "@/features/assistant/api";
import type { AssistantKey, ProviderModels } from "@/features/assistant/api";

const OTHER = "__other";
// Mirrors the server's model-name rule; the server enforces it.
const MODEL_NAME = /^[A-Za-z0-9][A-Za-z0-9._:/-]{0,99}$/;
const KEYS = ["assistant-keys"];

function useRefresh() {
  const qc = useQueryClient();
  return () => {
    void qc.invalidateQueries({ queryKey: KEYS });
    // The assistant panel reads its provider from the status query.
    void qc.invalidateQueries({ queryKey: ["assistant-status"] });
  };
}

function Labelled({ label, hint, children }: { label: string; hint?: ReactNode; children: ReactNode }) {
  return (
    <label className="grid gap-1.5 text-sm font-medium">
      {label}
      {children}
      {hint && <span className="text-xs font-normal text-muted-foreground">{hint}</span>}
    </label>
  );
}

/** API keys for the flow assistant, one of which the assistant uses. */
export function AssistantKeys() {
  const list = useQuery({ queryKey: KEYS, queryFn: keys.list });
  const catalog = useQuery({ queryKey: ["assistant-providers"], queryFn: keys.providers, staleTime: Infinity });
  const server = useQuery({ queryKey: ["assistant-status", "connections"], queryFn: status, retry: false });
  const keychain = useQuery({ queryKey: ["assistant-keychain"], queryFn: keys.keychain, retry: false });
  const canStore = keychain.data?.available === true;
  const refresh = useRefresh();
  const [editing, setEditing] = useState<AssistantKey | "new" | null>(null);
  const [removing, setRemoving] = useState<AssistantKey | null>(null);
  const section = useRef<HTMLElement>(null);
  const activate = useMutation({ mutationFn: keys.activate, onSuccess: refresh });
  const toggle = useMutation({
    mutationFn: (k: AssistantKey) => keys.update(k.id, { is_enabled: !k.is_enabled }),
    onSuccess: refresh,
  });
  const remove = useMutation({
    mutationFn: (k: AssistantKey) => keys.remove(k.id),
    onSuccess: () => {
      setRemoving(null);
      refresh();
    },
  });
  useEffect(() => {
    if (!list.isPending && window.location.hash === "#assistant") {
      section.current?.scrollIntoView({ block: "start" });
    }
  }, [list.isPending]);

  const providers = catalog.data ?? [];
  const label = (id: string) => providers.find((p) => p.id === id)?.label ?? id;
  const rows = list.data ?? [];
  const busy = activate.isPending || toggle.isPending || remove.isPending;
  const serverKey =
    server.data && server.data.provider !== "off" && server.data.source !== "local" ? server.data : null;

  return (
    <section ref={section} id="assistant" aria-labelledby="assistant-keys-title" className="mb-10 scroll-mt-6">
      <div className="mb-3 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 id="assistant-keys-title" className="text-lg font-semibold">
            Assistant API keys
          </h2>
          <p className="text-sm text-muted-foreground">
            Provider keys for the flow assistant, kept in this computer&apos;s keychain. The assistant uses one
            key at a time.
          </p>
        </div>
        <Button
          onClick={() => setEditing("new")}
          disabled={!providers.length || !canStore}
          aria-describedby={keychain.data?.detail ? "assistant-keychain" : undefined}
        >
          <Plus className="mr-1.5 h-4 w-4" /> Add API key
        </Button>
      </div>
      {keychain.data?.detail && (
        <p id="assistant-keychain" role="note" className="mb-3 text-sm text-amber-800 dark:text-amber-200">
          Keys can&apos;t be saved yet. {keychain.data.detail}
        </p>
      )}

      {list.isPending ? (
        <LoadingState label="Loading API keys…" />
      ) : list.isError ? (
        <ErrorState error={list.error} title="Couldn't load API keys" onRetry={() => list.refetch()} />
      ) : rows.length === 0 ? (
        <p className="rounded-lg border border-dashed border-border p-4 text-sm text-muted-foreground">
          {serverKey
            ? `The assistant uses a ${label(serverKey.provider)} key configured on the server. Add a key here to use your own.`
            : "No API keys yet. Add one to build flows with the assistant."}
        </p>
      ) : (
        <fieldset className="flex flex-col gap-2" disabled={busy}>
          <legend className="sr-only">Key the assistant uses</legend>
          {rows.map((k) => {
            const custom = !providers.find((p) => p.id === k.provider)?.models.includes(k.model);
            return (
              <div
                key={k.id}
                className={`flex flex-wrap items-center gap-3 rounded-lg border bg-card p-3 ${
                  k.is_active ? "border-primary/60 ring-1 ring-primary/30" : "border-border"
                }`}
              >
                <label className="flex min-w-0 flex-1 cursor-pointer items-center gap-3">
                  <input
                    type="radio"
                    name="assistant-key"
                    className="size-4 accent-primary"
                    checked={k.is_active}
                    disabled={!k.is_enabled}
                    onChange={() => activate.mutate(k.id)}
                    aria-describedby={`assistant-key-${k.id}`}
                  />
                  <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-muted text-primary">
                    <KeyRound aria-hidden className="size-4" />
                  </span>
                  <span className="min-w-0">
                    <span className="flex flex-wrap items-center gap-2 font-medium">
                      {k.name}
                      {k.is_active && (
                        <span className="rounded bg-emerald-100 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-800 dark:bg-emerald-900/50 dark:text-emerald-200">
                          In use
                        </span>
                      )}
                      {!k.is_enabled && (
                        <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground">
                          Disabled
                        </span>
                      )}
                    </span>
                    <span id={`assistant-key-${k.id}`} className="block truncate text-xs text-muted-foreground">
                      {label(k.provider)} · {k.model}
                      {custom && " (custom model)"}
                      {k.effort !== "default" && ` · ${k.effort} effort`}
                    </span>
                  </span>
                </label>
                <label className="flex items-center gap-2 text-xs text-muted-foreground">
                  <input
                    type="checkbox"
                    role="switch"
                    className="size-4 accent-primary"
                    checked={k.is_enabled}
                    aria-label={`${k.name} enabled`}
                    onChange={() => toggle.mutate(k)}
                  />
                  Enabled
                </label>
                <Button size="sm" variant="ghost" aria-label={`Edit ${k.name}`} onClick={() => setEditing(k)}>
                  <Pencil className="h-3.5 w-3.5 text-muted-foreground" />
                </Button>
                <Button size="sm" variant="ghost" aria-label={`Remove ${k.name}`} onClick={() => setRemoving(k)}>
                  <Trash2 className="h-3.5 w-3.5 text-muted-foreground" />
                </Button>
              </div>
            );
          })}
          {!rows.some((k) => k.is_active) && (
            <p role="status" className="text-xs text-muted-foreground">
              {serverKey
                ? `No key selected: the assistant uses the ${label(serverKey.provider)} key configured on the server.`
                : "No key selected: choose an enabled key to turn the assistant on."}
            </p>
          )}
        </fieldset>
      )}

      {editing && (
        <KeyDialog
          key={editing === "new" ? "new" : editing.id}
          current={editing === "new" ? undefined : editing}
          providers={providers}
          onClose={() => setEditing(null)}
          onSaved={refresh}
        />
      )}
      <ConfirmDialog
        open={removing !== null}
        onOpenChange={(o) => {
          if (!o) setRemoving(null);
        }}
        title={`Remove ${removing?.name ?? "API key"}?`}
        description={
          removing?.is_active
            ? "The key is deleted from this computer's keychain and the assistant stops using it. Revoke it at the provider too if it may have leaked."
            : "The key is deleted from this computer's keychain. Revoke it at the provider too if it may have leaked."
        }
        confirmLabel="Remove key"
        variant="destructive"
        isPending={remove.isPending}
        onConfirm={() => removing && remove.mutate(removing)}
      />
    </section>
  );
}

function KeyDialog({
  current,
  providers,
  onClose,
  onSaved,
}: {
  current?: AssistantKey;
  providers: ProviderModels[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const id = useId();
  const [name, setName] = useState(current?.name ?? "");
  const [provider, setProvider] = useState(current?.provider ?? providers[0]?.id ?? "");
  const spec = providers.find((p) => p.id === provider);
  const known = spec?.models ?? [];
  const [choice, setChoice] = useState(
    current ? (known.includes(current.model) ? current.model : OTHER) : (known[0] ?? OTHER),
  );
  const [typed, setTyped] = useState(current && !known.includes(current.model) ? current.model : "");
  const [effort, setEffort] = useState(current?.effort ?? "default");
  const [secret, setSecret] = useState("");
  const [agreed, setAgreed] = useState(false);
  const [error, setError] = useState("");
  const model = choice === OTHER ? typed.trim() : choice;
  const needsAgreement = !current || secret !== "";

  const save = useMutation({
    mutationFn: () => {
      const replace = secret ? { key: secret, acknowledged: true } : {};
      return current
        ? keys.update(current.id, { name: name.trim(), model, effort, ...replace })
        : keys.create({ name: name.trim(), provider, model, effort, ...replace });
    },
    meta: { suppressErrorToast: true },
    onSuccess: () => {
      onSaved();
      onClose();
    },
    onError: (e) => setError(e instanceof ApiError ? e.message : "Saving failed. Try again."),
  });

  function submit(e: FormEvent) {
    e.preventDefault();
    setError("");
    if (!name.trim()) return setError("Enter a name for this key.");
    if (!MODEL_NAME.test(model)) {
      return setError("Enter a model name of letters, digits and . _ : / - characters.");
    }
    if (!current && !secret) return setError("Enter the API key.");
    if (secret && secret !== secret.trim()) return setError("Remove spaces around the API key.");
    if (needsAgreement && !agreed) return setError("Confirm the storage notice to save the key.");
    save.mutate();
  }

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{current ? `Edit ${current.name}` : "Add an assistant API key"}</DialogTitle>
          <DialogDescription>
            Use a provider API key with API billing. Chat subscriptions are billed separately.
          </DialogDescription>
        </DialogHeader>
        <form className="grid gap-4" onSubmit={submit} autoComplete="off" noValidate>
          <Labelled label="Name">
            <Input
              value={name}
              maxLength={80}
              autoComplete="off"
              onChange={(e) => setName(e.target.value)}
              placeholder="Work OpenAI"
            />
          </Labelled>
          <Labelled label="Provider" hint={current ? "A saved key keeps its provider. Add a new key for another one." : undefined}>
            <Select
              value={provider}
              disabled={!!current}
              onChange={(e) => {
                const next = providers.find((p) => p.id === e.target.value);
                setProvider(e.target.value);
                setChoice(next?.models[0] ?? OTHER);
                setEffort("default");
              }}
            >
              {providers.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.label}
                </option>
              ))}
            </Select>
          </Labelled>
          <Labelled label="Model">
            <Select value={choice} onChange={(e) => setChoice(e.target.value)}>
              {known.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
              <option value={OTHER}>Other model…</option>
            </Select>
          </Labelled>
          {choice === OTHER && (
            <Labelled
              label="Model name"
              hint="Type the exact model ID from the provider. Models outside the list are not tested with Ciaren."
            >
              <Input
                value={typed}
                maxLength={100}
                spellCheck={false}
                autoComplete="off"
                onChange={(e) => setTyped(e.target.value)}
              />
            </Labelled>
          )}
          {!!spec?.efforts.length && (
            <Labelled label="Reasoning effort">
              <Select value={effort} onChange={(e) => setEffort(e.target.value)}>
                <option value="default">Provider default</option>
                {spec.efforts.map((x) => (
                  <option key={x} value={x}>
                    {x}
                  </option>
                ))}
              </Select>
            </Labelled>
          )}
          <Labelled label={current ? "New API key (optional)" : "API key"} hint={current ? "Leave empty to keep the saved key." : undefined}>
            <Input
              type="password"
              value={secret}
              maxLength={4096}
              // Not a sign-in form: keep browsers and password managers from filling a saved password.
              autoComplete="new-password"
              data-1p-ignore
              data-lpignore="true"
              data-bwignore
              spellCheck={false}
              onChange={(e) => setSecret(e.target.value)}
            />
          </Labelled>
          {needsAgreement && (
            <div
              role="note"
              aria-labelledby={`${id}-notice`}
              className="grid gap-2 rounded-lg border border-amber-300 bg-amber-50 p-3 text-xs text-amber-950 dark:border-amber-700 dark:bg-amber-950/40 dark:text-amber-100"
            >
              <p id={`${id}-notice`} className="flex items-center gap-1.5 font-semibold">
                <ShieldAlert aria-hidden className="size-4" /> Before you save this key
              </p>
              <ul className="list-disc space-y-1 pl-4">
                <li>
                  It is stored only on the computer that runs Ciaren, in its keychain (Windows Credential Manager,
                  macOS Keychain or Secret Service). Ciaren never shows it again.
                </li>
                <li>It is sent only to {spec?.label ?? "the provider"}, with each assistant request.</li>
                <li>Anyone who can use this Ciaren server can run the assistant with it, on your bill.</li>
                <li>Prefer a key with a spending limit, and revoke it at the provider if it leaks.</li>
              </ul>
              <label className="flex items-start gap-2 text-sm font-medium">
                <input
                  type="checkbox"
                  className="mt-0.5 size-4 accent-primary"
                  checked={agreed}
                  onChange={(e) => setAgreed(e.target.checked)}
                />
                I understand and want to save this key on this computer
              </label>
            </div>
          )}
          {error && (
            <p role="alert" className="text-sm text-destructive">
              {error}
            </p>
          )}
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={onClose} disabled={save.isPending}>
              Cancel
            </Button>
            <Button type="submit" disabled={save.isPending}>
              {current ? "Save changes" : "Save key"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
