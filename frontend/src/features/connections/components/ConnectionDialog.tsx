import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, ArrowLeft, RefreshCw } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { ApiError } from "@/lib/api/client";
import type { Connection, ConnectionCreate, ProviderInfo } from "@/features/connections/types";
import {
  useConnectionProviders,
  useCreateConnection,
  useTestConnectionConfig,
  useUpdateConnection,
} from "../hooks";
import { getProviderMeta, ProviderIconBadge } from "./providerMeta";
import { TestButton } from "./TestButton";
import { Field } from "./Field";
import { SecretRefField } from "./SecretRefField";
import { ProviderSection } from "./ConnectionProviderPicker";
import { ApiFields } from "./ApiFields";
import { SnowflakeFields } from "./SnowflakeFields";
import { PluginProviderFields } from "./PluginProviderFields";
import { StorageFields } from "./StorageFields";

const EMPTY: ConnectionCreate = {
  name: "",
  provider: "postgresql",
  host: "",
  port: null,
  database: "",
  username: "",
  password_env: "",
  options: null,
};

function connectionToForm(c: Connection): ConnectionCreate {
  return {
    name: c.name,
    provider: c.provider,
    host: c.host,
    port: c.port,
    database: c.database,
    username: c.username,
    password_env: c.password_env,
    options: c.options as Record<string, unknown> | null | undefined,
  };
}

type DialogStep = "pick" | "configure";

export function ConnectionDialog({
  open,
  onOpenChange,
  providers,
  connection,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  providers: ProviderInfo[];
  connection?: Connection;
}) {
  const isEdit = !!connection;
  const create = useCreateConnection();
  const update = useUpdateConnection();
  const testConfig = useTestConnectionConfig();
  // Same query key as ConnectionsPage — TanStack deduplicates, no extra request.
  // Having refetch here lets the picker recheck driver availability after install.
  const { refetch: recheckProviders, isFetching: isRechecking } = useConnectionProviders();
  const [step, setStep] = useState<DialogStep>(isEdit ? "configure" : "pick");
  const [form, setForm] = useState<ConnectionCreate>(isEdit ? connectionToForm(connection!) : EMPTY);

  const set = (patch: Partial<ConnectionCreate>) => {
    testConfig.reset();
    setForm((f) => ({ ...f, ...patch }));
  };

  const setOption = (key: string, value: string) =>
    set({ options: { ...(form.options ?? {}), [key]: value || undefined } });

  // Schema-driven plugin fields can hold any JSON value (booleans, numbers, lists).
  const setOptionValue = (key: string, value: unknown) =>
    set({ options: { ...(form.options ?? {}), [key]: value === "" ? undefined : value } });

  const provider = useMemo(
    () => providers.find((p) => p.name === form.provider),
    [providers, form.provider],
  );
  const isStorage = provider?.kind === "storage";
  const isMlflow = provider?.kind === "mlflow";
  const isApi = provider?.kind === "api" && !provider?.plugin;
  const isSqlite = form.provider === "sqlite" || form.provider === "duckdb";
  const isSnowflake = form.provider === "snowflake" && !provider?.plugin;

  const selectableProviders = providers;
  const dbProviders = selectableProviders.filter((p) => !p.plugin && (p.kind === "sql" || p.kind === "mongo"));
  const apiProviders = selectableProviders.filter((p) => !p.plugin && p.kind === "api");
  const storageProviders = selectableProviders.filter((p) => !p.plugin && p.kind === "storage");
  const trackingProviders = selectableProviders.filter((p) => !p.plugin && p.kind === "mlflow");
  const pluginProviders = selectableProviders.filter((p) => p.plugin);

  const selectProvider = (p: ProviderInfo) => {
    testConfig.reset();
    setForm({
      ...EMPTY,
      name: form.name,
      provider: p.name,
      port: p.default_port ?? null,
    });
    setStep("configure");
  };

  const goBack = () => {
    testConfig.reset();
    setStep("pick");
  };

  const payload = (): ConnectionCreate => ({ ...form, port: form.port ? Number(form.port) : null });

  const submit = async () => {
    try {
      if (isEdit) {
        await update.mutateAsync({ id: connection!.id, body: payload() });
      } else {
        await create.mutateAsync(payload());
      }
      onOpenChange(false);
    } catch {
      /* error shown in UI */
    }
  };

  // Sync state whenever the dialog opens (or the connection being edited changes).
  // On close: do a delayed reset to defaults so the animation finishes cleanly;
  // the cleanup cancels it if the dialog reopens before the timeout fires.
  useEffect(() => {
    if (open) {
      setStep(isEdit ? "configure" : "pick");
      setForm(isEdit ? connectionToForm(connection!) : EMPTY);
      testConfig.reset();
    } else {
      const t = setTimeout(() => {
        setStep("pick");
        setForm(EMPTY);
      }, 200);
      return () => clearTimeout(t);
    }
  }, [open, connection]); // eslint-disable-line react-hooks/exhaustive-deps

  const meta = getProviderMeta(form.provider);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className={cn("transition-none", step === "pick" ? "sm:max-w-3xl" : "sm:max-w-lg")}
      >
        {step === "pick" ? (
          <>
            <DialogHeader>
              <div className="flex items-start justify-between gap-2">
                <div>
                  <DialogTitle>Add connection</DialogTitle>
                  <DialogDescription>
                    Choose the type of database or storage you want to connect to.
                  </DialogDescription>
                </div>
                <button
                  type="button"
                  onClick={() => recheckProviders()}
                  disabled={isRechecking}
                  title="Recheck which drivers are installed"
                  className="flex shrink-0 items-center gap-1 rounded-md border border-border px-2 py-1.5 text-[11px] font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:opacity-50"
                >
                  <RefreshCw className={cn("h-3 w-3", isRechecking && "animate-spin")} />
                  Recheck
                </button>
              </div>
            </DialogHeader>

            {/* Scrollable provider grid */}
            <div className="max-h-[70vh] overflow-y-auto pr-1">
              <div className="flex flex-col gap-5 pb-1 pt-1">
                <ProviderSection
                  label="Databases"
                  providers={dbProviders}
                  onSelect={selectProvider}
                />
                <ProviderSection
                  label="APIs"
                  providers={apiProviders}
                  onSelect={selectProvider}
                />
                <ProviderSection
                  label="Storage"
                  providers={storageProviders}
                  onSelect={selectProvider}
                />
                <ProviderSection
                  label="Experiment tracking"
                  providers={trackingProviders}
                  onSelect={selectProvider}
                />
                <ProviderSection
                  label="From plugins"
                  providers={pluginProviders}
                  onSelect={selectProvider}
                />
              </div>
            </div>
          </>
        ) : (
          <>
            <DialogHeader>
              <div className="flex items-start gap-2">
                {!isEdit && (
                  <button
                    type="button"
                    onClick={goBack}
                    className="mt-0.5 rounded-md p-1 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                    title="Choose a different connector"
                  >
                    <ArrowLeft className="h-4 w-4" />
                  </button>
                )}
                <div>
                  <DialogTitle>{isEdit ? "Edit connection" : "Configure connection"}</DialogTitle>
                  <DialogDescription>
                    {isMlflow
                      ? "Where Ciaren logs experiments and models. Used by all ML flows."
                      : isStorage
                        ? "Secret keys are read at runtime (env var, OS keychain, or secret file) and never stored."
                        : "Passwords are read at runtime (env var, OS keychain, or secret file) and never stored."}
                  </DialogDescription>
                </div>
              </div>
            </DialogHeader>

            {/* Selected provider chip */}
            <div className="flex items-center gap-2.5 rounded-lg border border-border bg-muted/30 px-3 py-2">
              <ProviderIconBadge name={form.provider} size="sm" />
              <div className="flex-1">
                <p className="text-xs font-semibold">{provider?.label}</p>
                <p className="text-[10px] text-muted-foreground">{meta.description}</p>
              </div>
              {!isEdit && (
                <button
                  type="button"
                  onClick={goBack}
                  className="text-[11px] font-medium text-primary hover:underline"
                >
                  Change
                </button>
              )}
            </div>

            {provider && !provider.available && provider.extra && (
              <div className="flex items-center gap-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-[11px] text-amber-700">
                <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
                <span className="flex-1">
                  Driver not installed.{" "}
                  <code className="font-mono">pip install ciaren[{provider.extra}]</code>
                </span>
              </div>
            )}

            <div className="flex flex-col gap-3">
              <Field label="Connection name">
                <Input
                  value={form.name}
                  onChange={(e) => set({ name: e.target.value })}
                  placeholder={isStorage ? "my-s3-bucket" : isMlflow ? "Local MLflow" : "warehouse"}
                  autoFocus
                />
              </Field>

              {provider?.plugin ? (
                <PluginProviderFields
                  form={form}
                  provider={provider}
                  set={set}
                  setOptionValue={setOptionValue}
                />
              ) : isApi ? (
                <ApiFields form={form} set={set} setOptionValue={setOptionValue} />
              ) : isMlflow ? (
                <Field
                  label="Tracking URI"
                  hint="A local folder (./mlruns), sqlite:///path/mlflow.db, or a tracking server (http://host:5000)."
                >
                  <Input
                    value={form.database ?? ""}
                    onChange={(e) => set({ database: e.target.value })}
                    placeholder="./mlruns"
                  />
                </Field>
              ) : isStorage ? (
                <StorageFields form={form} provider={provider!} set={set} setOption={setOption} />
              ) : isSqlite ? (
                <Field label="Database file path">
                  <Input
                    value={form.database ?? ""}
                    onChange={(e) => set({ database: e.target.value })}
                    placeholder="/data/warehouse.db"
                  />
                </Field>
              ) : isSnowflake ? (
                <SnowflakeFields form={form} set={set} setOption={setOption} />
              ) : (
                <>
                  <div className="grid grid-cols-2 gap-3">
                    <Field label="Host">
                      <Input
                        value={form.host ?? ""}
                        onChange={(e) => set({ host: e.target.value })}
                        placeholder="localhost"
                      />
                    </Field>
                    <Field label="Port">
                      <Input
                        type="number"
                        value={form.port ?? ""}
                        onChange={(e) =>
                          set({ port: e.target.value ? Number(e.target.value) : null })
                        }
                      />
                    </Field>
                  </div>
                  <Field label="Database">
                    <Input
                      value={form.database ?? ""}
                      onChange={(e) => set({ database: e.target.value })}
                    />
                  </Field>
                  <Field label="Username">
                    <Input
                      value={form.username ?? ""}
                      onChange={(e) => set({ username: e.target.value })}
                    />
                  </Field>
                  <SecretRefField
                    label="Password secret"
                    hint="Env var name, keyring:NAME (OS keychain), or file:/path"
                    placeholder="PG_PASSWORD"
                    value={form.password_env ?? ""}
                    onChange={(v) => set({ password_env: v })}
                    suggestedName={form.name}
                  />
                </>
              )}

              {(isEdit ? update.isError : create.isError) && (
                <p className="text-xs text-destructive">
                  {((isEdit ? update.error : create.error) as ApiError)?.message ??
                    (isEdit ? "Could not update connection." : "Could not create connection.")}
                </p>
              )}

              <div className="mt-1 flex items-center justify-end gap-2">
                <TestButton
                  className="mr-auto"
                  onTest={() => testConfig.mutate(payload())}
                  isPending={testConfig.isPending}
                  result={testConfig.data}
                  error={testConfig.error}
                  disabled={!form.provider}
                />
                <Button variant="ghost" onClick={() => onOpenChange(false)}>
                  Cancel
                </Button>
                <Button
                  onClick={submit}
                  disabled={
                    (isEdit ? update.isPending : create.isPending) ||
                    !form.name ||
                    !testConfig.data?.ok
                  }
                  title={!testConfig.data?.ok ? "Test the connection first" : undefined}
                >
                  {(isEdit ? update.isPending : create.isPending) ? "Saving…" : "Save connection"}
                </Button>
              </div>
            </div>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
