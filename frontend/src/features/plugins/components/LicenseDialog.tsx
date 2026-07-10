import { useState } from "react";
import { KeyRound, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { ApiError } from "@/lib/api/client";
import type { PluginInfo } from "@/features/plugins/types";
import { useActivateLicense } from "../hooks";

// Paste-a-token activation. The backend vets the token against the trusted
// issuer keys before caching it, so a bad paste can't clobber a working license.
export function LicenseDialog({
  plugin,
  open,
  onOpenChange,
}: {
  plugin: PluginInfo;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const activate = useActivateLicense();
  const [raw, setRaw] = useState("");
  const [error, setError] = useState<string | null>(null);

  const onActivate = () => {
    setError(null);
    let token: unknown;
    try {
      token = JSON.parse(raw);
    } catch {
      setError("That doesn't look like a license token (invalid JSON).");
      return;
    }
    activate.mutate(
      { id: plugin.id, token },
      {
        onSuccess: (status) => {
          if (status.valid) {
            onOpenChange(false);
            setRaw("");
          } else {
            setError(status.reason ?? "The license did not validate.");
          }
        },
        onError: (err) =>
          setError(err instanceof ApiError ? err.message : "Couldn't activate the license."),
      },
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <KeyRound className="h-4 w-4" /> Activate license — {plugin.name}
          </DialogTitle>
        </DialogHeader>
        <p className="text-sm text-muted-foreground">
          Paste the license token you received after purchase (a small JSON document). It is
          stored only on this machine and keeps working offline within its grace period.
        </p>
        <textarea
          value={raw}
          onChange={(e) => setRaw(e.target.value)}
          rows={7}
          spellCheck={false}
          placeholder='{"userId": "...", "pluginId": "...", "signature": "..."}'
          className="w-full rounded-md border border-border bg-background p-2 font-mono text-xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        />
        {error && <p className="text-xs text-red-600">{error}</p>}
        <div className="flex justify-end gap-2">
          <Button size="sm" variant="ghost" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button size="sm" disabled={activate.isPending || !raw.trim()} onClick={onActivate}>
            {activate.isPending ? (
              <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
            ) : (
              <KeyRound className="mr-1.5 h-3.5 w-3.5" />
            )}
            Activate
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
