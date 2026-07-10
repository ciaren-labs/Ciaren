import { useRef, useState } from "react";
import { Loader2, ShieldAlert, Upload } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import { ApiError } from "@/lib/api/client";
import { useInstallPlugin } from "../hooks";

export function InstallButton() {
  const inputRef = useRef<HTMLInputElement>(null);
  const install = useInstallPlugin();
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);
  // A picked file is held here until the user acknowledges the risk in the confirm
  // dialog — installing never starts straight from the file picker.
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const [acknowledged, setAcknowledged] = useState(false);
  const [dialogError, setDialogError] = useState<string | null>(null);

  const onPick = (file: File | undefined) => {
    if (!file) return;
    setMessage(null);
    setDialogError(null);
    setAcknowledged(false); // the toggle always starts off, per file
    setPendingFile(file);
  };

  const closeDialog = () => {
    setPendingFile(null);
    setAcknowledged(false);
    setDialogError(null);
  };

  const confirmInstall = () => {
    if (!pendingFile || !acknowledged) return;
    setDialogError(null);
    install.mutate(pendingFile, {
      onSuccess: (res) => {
        setMessage({ ok: true, text: `Installed ${res.plugin.name} (${res.outcome}).` });
        closeDialog();
      },
      onError: (err) => setDialogError(err instanceof ApiError ? err.message : "Install failed."),
    });
  };

  return (
    <div className="flex flex-col items-end gap-1">
      <input
        ref={inputRef}
        type="file"
        accept=".ciarenplugin"
        className="hidden"
        onChange={(e) => {
          onPick(e.target.files?.[0]);
          e.target.value = ""; // allow re-picking the same file
        }}
      />
      <Button size="sm" disabled={install.isPending} onClick={() => inputRef.current?.click()}>
        <Upload className="mr-1.5 h-3.5 w-3.5" />
        Install plugin
      </Button>
      {message && (
        <span className={cn("text-xs", message.ok ? "text-emerald-600" : "text-red-600")}>
          {message.text}
        </span>
      )}
      <InstallConfirmDialog
        file={pendingFile}
        acknowledged={acknowledged}
        onAcknowledgedChange={setAcknowledged}
        isPending={install.isPending}
        error={dialogError}
        onCancel={closeDialog}
        onConfirm={confirmInstall}
      />
    </div>
  );
}

// A deliberate speed bump before installing an uploaded package: it spells out that
// the plugin will run unsandboxed, and gates the install behind a toggle that
// starts OFF, so a user can't one-click past the risk. It does not run the code
// (approval does) — it's the "do you trust this file?" checkpoint.
function InstallConfirmDialog({
  file,
  acknowledged,
  onAcknowledgedChange,
  isPending,
  error,
  onCancel,
  onConfirm,
}: {
  file: File | null;
  acknowledged: boolean;
  onAcknowledgedChange: (value: boolean) => void;
  isPending: boolean;
  error: string | null;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  return (
    <Dialog open={file !== null} onOpenChange={(open) => !open && onCancel()}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <ShieldAlert className="h-4 w-4 text-amber-600" /> Install this plugin?
          </DialogTitle>
        </DialogHeader>
        <div className="flex items-start gap-3 rounded-md border border-amber-300 bg-amber-50 p-3 text-[13px] text-amber-900 dark:border-amber-900 dark:bg-amber-950/60 dark:text-amber-200">
          <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" />
          <div>
            <p>
              You are about to install{" "}
              <span className="break-all font-mono font-medium">{file?.name}</span>.
            </p>
            <p className="mt-1 leading-relaxed">
              A plugin is ordinary Python that, once you approve it, runs on this machine
              with your account's access — it is <strong>not sandboxed</strong>. A
              malicious or buggy plugin could read or delete your files, use your saved
              credentials, run other programs, or send data over the network.
            </p>
            <p className="mt-1 leading-relaxed">
              Install only plugins from a source you trust and whose code you can review —
              a <code className="rounded bg-amber-100 px-1 dark:bg-amber-900">.ciarenplugin</code>{" "}
              is a zip you can unzip and read. Prefer signed packages from a trusted publisher.
            </p>
          </div>
        </div>
        <label className="flex cursor-pointer items-start gap-2 text-sm">
          <input
            type="checkbox"
            checked={acknowledged}
            onChange={(e) => onAcknowledgedChange(e.target.checked)}
            className="mt-0.5 h-4 w-4 shrink-0 accent-primary"
          />
          <span>
            I trust the source of this plugin and understand it will run on my machine
            unsandboxed, with my account's access.
          </span>
        </label>
        {error && <p className="text-xs text-red-600">{error}</p>}
        <div className="flex justify-end gap-2">
          <Button size="sm" variant="ghost" onClick={onCancel}>
            Cancel
          </Button>
          <Button size="sm" disabled={!acknowledged || isPending} onClick={onConfirm}>
            {isPending ? (
              <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
            ) : (
              <Upload className="mr-1.5 h-3.5 w-3.5" />
            )}
            Install plugin
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
