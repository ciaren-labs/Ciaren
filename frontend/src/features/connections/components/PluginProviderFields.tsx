import { Input } from "@/components/ui/input";
import { SchemaConfigFields } from "@/components/flow/SchemaConfigFields";
import type { ConnectionCreate, ProviderInfo } from "@/features/connections/types";
import { Field } from "./Field";
import { SecretRefField } from "./SecretRefField";

/** Form for a plugin-contributed connector: the standard fields its provider
 *  flags ask for (host/port, database or bucket, username + password env var)
 *  plus the connector's own `config_schema` fields, which are stored in the
 *  connection's `options`. */
export function PluginProviderFields({
  form,
  provider,
  set,
  setOptionValue,
}: {
  form: ConnectionCreate;
  provider: ProviderInfo;
  set: (patch: Partial<ConnectionCreate>) => void;
  setOptionValue: (key: string, value: unknown) => void;
}) {
  const schemaFields = provider.config_schema?.fields ?? [];
  const isStorageKind = provider.kind === "storage";
  return (
    <>
      {provider.needs_host && (
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
              onChange={(e) => set({ port: e.target.value ? Number(e.target.value) : null })}
            />
          </Field>
        </div>
      )}
      {(provider.needs_bucket || isStorageKind) && (
        <Field label={isStorageKind ? "Bucket / folder" : "Bucket"}>
          <Input
            value={form.database ?? ""}
            onChange={(e) => set({ database: e.target.value })}
          />
        </Field>
      )}
      {(provider.kind === "sql" || provider.kind === "mongo") && (
        <Field label="Database">
          <Input value={form.database ?? ""} onChange={(e) => set({ database: e.target.value })} />
        </Field>
      )}
      {provider.needs_auth && (
        <>
          <Field label="Username">
            <Input
              value={form.username ?? ""}
              onChange={(e) => set({ username: e.target.value })}
            />
          </Field>
          <SecretRefField
            label="Password secret"
            hint="Env var name, keyring:NAME (OS keychain), or file:/path"
            placeholder="MY_SECRET"
            value={form.password_env ?? ""}
            onChange={(v) => set({ password_env: v })}
            suggestedName={form.name}
          />
        </>
      )}
      <SchemaConfigFields
        fields={schemaFields}
        config={(form.options ?? {}) as Record<string, unknown>}
        onChange={setOptionValue}
      />
    </>
  );
}
