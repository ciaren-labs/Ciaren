import { useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { status, updateCredential } from "./api";

export function CredentialSettings({ provider }: { provider: string }) {
  const query = useQuery({
    queryKey: ["assistant-status", provider],
    queryFn: status,
    retry: false,
  });
  const input = useRef<HTMLInputElement>(null);
  const [feedback, setFeedback] = useState("");
  const [busy, setBusy] = useState(false);
  const data = query.data;
  async function update(remove: boolean) {
    if (!data || data.provider !== provider || !input.current) return;
    const field = input.current;
    const value = remove ? undefined : field.value;
    field.value = "";
    if (!remove && !value) {
      setFeedback("Enter an API key first.");
      field.focus();
      return;
    }
    setBusy(true);
    try {
      await updateCredential(data.provider, value);
      await query.refetch();
      setFeedback(remove ? "Credential removed." : "Credential saved.");
    } catch {
      setFeedback(
        "Credential update failed. Check the secure OS keychain and try again.",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="space-y-2 p-4 text-sm">
      <h3 className="font-medium">Provider API credential</h3>
      <p className="text-xs text-muted-foreground">
        Use a billed API key. ChatGPT and Claude chat subscriptions have
        separate billing. Everyone with access to this Ciaren instance shares
        these settings.
      </p>
      <div role="status">
        {query.isError
          ? "Credential status unavailable."
          : !data
            ? "Checking credential…"
            : data.provider === "off"
              ? "Assistant is off."
              : `${data.provider} · ${data.source} · ${data.state}`}
      </div>
      {data?.provider === provider && data.source === "keyring" && (
        <form
          className="flex flex-wrap items-end gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            void update(false);
          }}
        >
          <label className="grid gap-1">
            New API key
            <Input
              key={provider}
              ref={input}
              type="password"
              autoComplete="off"
              spellCheck={false}
              maxLength={4096}
              disabled={busy}
            />
          </label>
          <Button size="sm" disabled={busy} type="submit">
            Save key
          </Button>
          {data.state === "configured" && (
            <Button
              size="sm"
              variant="outline"
              type="button"
              disabled={busy}
              onClick={() => void update(true)}
            >
              Remove key
            </Button>
          )}
        </form>
      )}
      {data?.source && data.source !== "keyring" && (
        <p>Rotate or revoke this key at its server source.</p>
      )}
      <p role="status">{feedback}</p>
    </div>
  );
}
