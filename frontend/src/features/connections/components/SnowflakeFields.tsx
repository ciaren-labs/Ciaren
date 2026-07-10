import { Input } from "@/components/ui/input";
import type { ConnectionCreate } from "@/features/connections/types";
import { Field } from "./Field";
import { SecretRefField } from "./SecretRefField";

/** Snowflake's connector treats `host` as the account identifier and has no
 *  use for `port` (there's no field for it at all — the backend URL builder
 *  never includes one, see sql.py's snowflake branch); warehouse/schema/role
 *  ride along as query options instead of the generic host/port form. */
export function SnowflakeFields({
  form,
  set,
  setOption,
}: {
  form: ConnectionCreate;
  set: (patch: Partial<ConnectionCreate>) => void;
  setOption: (key: string, value: string) => void;
}) {
  const opts = (form.options ?? {}) as Record<string, string>;
  return (
    <>
      <Field label="Account identifier" hint="e.g. xy12345.us-east-1">
        <Input
          value={form.host ?? ""}
          onChange={(e) => set({ host: e.target.value })}
          placeholder="xy12345.us-east-1"
        />
      </Field>
      <Field label="Database">
        <Input value={form.database ?? ""} onChange={(e) => set({ database: e.target.value })} />
      </Field>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Warehouse" hint="Optional">
          <Input
            value={opts.warehouse ?? ""}
            onChange={(e) => setOption("warehouse", e.target.value)}
            placeholder="COMPUTE_WH"
          />
        </Field>
        <Field label="Role" hint="Optional">
          <Input
            value={opts.role ?? ""}
            onChange={(e) => setOption("role", e.target.value)}
            placeholder="SYSADMIN"
          />
        </Field>
      </div>
      <Field label="Schema" hint="Optional">
        <Input
          value={opts.schema ?? ""}
          onChange={(e) => setOption("schema", e.target.value)}
          placeholder="PUBLIC"
        />
      </Field>
      <Field label="Username">
        <Input value={form.username ?? ""} onChange={(e) => set({ username: e.target.value })} />
      </Field>
      <SecretRefField
        label="Password secret"
        hint="Env var name, keyring:NAME (OS keychain), or file:/path"
        placeholder="SNOWFLAKE_PASSWORD"
        value={form.password_env ?? ""}
        onChange={(v) => set({ password_env: v })}
        suggestedName={form.name}
      />
    </>
  );
}
