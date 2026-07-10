import { useState } from "react";
import { Check, KeyRound } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { ApiError } from "@/lib/api/client";
import { useKeyringAvailability, useStoreKeyringSecret } from "../hooks";
import { Field } from "./Field";

/** Turn a connection name into a valid keychain entry name (keyring: grammar). */
function keyringNameFrom(name: string): string {
  const slug = name
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9._-]+/g, "-")
    .replace(/^[-.]+|[-.]+$/g, "");
  return slug || "secret";
}

/**
 * A connection secret field: the input holds a *reference*
 * (env var name, keyring:NAME, or file:/path). When the host has a usable OS
 * keychain, it also offers "Save a secret to the system keychain" — the entered
 * value is written straight to the OS keychain (never persisted by Ciaren) and
 * the field is set to the resulting keyring:NAME reference.
 */
export function SecretRefField({
  label,
  hint,
  placeholder,
  value,
  onChange,
  suggestedName,
  allowKeychain = true,
}: {
  label: string;
  hint?: string;
  placeholder?: string;
  value: string;
  onChange: (v: string) => void;
  suggestedName: string;
  allowKeychain?: boolean;
}) {
  const keyring = useKeyringAvailability();
  const store = useStoreKeyringSecret();
  const [open, setOpen] = useState(false);
  const [entryName, setEntryName] = useState("");
  const [secretValue, setSecretValue] = useState("");
  const [saved, setSaved] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  function openPanel() {
    setEntryName(keyringNameFrom(suggestedName));
    setSecretValue("");
    setError(null);
    setSaved(null);
    setOpen(true);
  }

  async function save(overwrite = false): Promise<void> {
    setError(null);
    try {
      const res = await store.mutateAsync({ name: entryName, value: secretValue, overwrite });
      onChange(res.reference);
      setSaved(res.reference);
      setSecretValue("");
      setOpen(false);
      // Drop the plaintext value react-query keeps as the mutation's `variables`.
      store.reset();
    } catch (e) {
      if (e instanceof ApiError && e.status === 409 && !overwrite) {
        if (confirm(`${e.message}\n\nOverwrite it?`)) return save(true);
        return;
      }
      setError(e instanceof ApiError ? e.message : "Could not save to the keychain.");
    }
  }

  function cancel() {
    setSecretValue(""); // don't leave the plaintext secret lingering in state
    setError(null);
    setOpen(false);
  }

  return (
    <Field label={label} hint={hint}>
      <Input value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} />
      {saved ? (
        <p className="mt-1 inline-flex items-center gap-1 text-[11px] font-medium text-emerald-600">
          <Check className="h-3 w-3" />
          Saved to the OS keychain as <code>{saved}</code>.
        </p>
      ) : (
        // Show the keychain option whenever it makes sense for this field
        // (GCS opts out — it holds a file path). When the OS keychain isn't
        // available it stays visible but disabled, with a hover explaining why,
        // rather than silently vanishing.
        allowKeychain &&
        keyring.data && (
          <>
            <div className="mt-1.5 flex items-center gap-2">
              <span className="h-px flex-1 bg-border" />
              <span className="text-[10px] uppercase tracking-wide text-muted-foreground">or</span>
              <span className="h-px flex-1 bg-border" />
            </div>
            {keyring.data.available ? (
              <button
                type="button"
                onClick={openPanel}
                className="mt-1.5 inline-flex w-full items-center justify-center gap-1.5 rounded-md border border-dashed border-primary/40 bg-primary/5 px-2.5 py-1.5 text-xs font-medium text-primary transition-colors hover:border-primary/60 hover:bg-primary/10"
              >
                <KeyRound className="h-3.5 w-3.5" />
                Store a value in the OS keychain
              </button>
            ) : (
              <Tooltip>
                <TooltipTrigger asChild>
                  <span className="mt-1.5 block w-full cursor-not-allowed">
                    <button
                      type="button"
                      disabled
                      className="inline-flex w-full items-center justify-center gap-1.5 rounded-md border border-dashed border-border bg-muted/40 px-2.5 py-1.5 text-xs font-medium text-muted-foreground"
                    >
                      <KeyRound className="h-3.5 w-3.5" />
                      Store a value in the OS keychain
                    </button>
                  </span>
                </TooltipTrigger>
                <TooltipContent className="max-w-xs text-center">
                  {keyring.data.detail ?? "The OS keychain isn't available on this host."}
                </TooltipContent>
              </Tooltip>
            )}
          </>
        )
      )}

      {/* Centered modal — keeps the panel out of the form's two-column grid so it
          isn't cramped against the right edge, and reads as a first-class option. */}
      <Dialog open={open} onOpenChange={(o) => (o ? setOpen(true) : cancel())}>
        <DialogContent className="max-w-sm gap-4">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-base">
              <KeyRound className="h-4 w-4 text-primary" />
              Store a secret in the OS keychain
            </DialogTitle>
            <DialogDescription>
              The value is written to your operating system&rsquo;s keychain and never stored by
              Ciaren. The connection keeps only a <code>keyring:NAME</code> reference.
            </DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-3">
            <Field label="Keychain name" hint="You'll reference it as keyring:NAME">
              <Input
                value={entryName}
                onChange={(e) => setEntryName(e.target.value)}
                placeholder="pg-main"
                autoFocus
              />
            </Field>
            <Field label="Secret value">
              <Input
                type="password"
                value={secretValue}
                onChange={(e) => setSecretValue(e.target.value)}
                placeholder="the password / token"
                autoComplete="new-password"
                maxLength={4096}
              />
            </Field>
            {error && <p className="text-xs text-destructive">{error}</p>}
          </div>
          <div className="flex items-center justify-end gap-2">
            <Button variant="ghost" onClick={cancel}>
              Cancel
            </Button>
            <Button
              onClick={() => void save(false)}
              disabled={!entryName || !secretValue || store.isPending}
            >
              {store.isPending ? "Saving…" : "Save to keychain"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </Field>
  );
}
