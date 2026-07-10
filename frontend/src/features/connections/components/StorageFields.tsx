import { Input } from "@/components/ui/input";
import type { ConnectionCreate, ProviderInfo } from "@/features/connections/types";
import { Field } from "./Field";
import { SecretRefField } from "./SecretRefField";

export function StorageFields({
  form,
  provider,
  set,
  setOption,
}: {
  form: ConnectionCreate;
  provider: ProviderInfo;
  set: (patch: Partial<ConnectionCreate>) => void;
  setOption: (key: string, value: string) => void;
}) {
  const opts = (form.options ?? {}) as Record<string, string>;

  if (provider.name === "local") {
    return (
      <Field
        label="Folder path"
        hint="Absolute path to a directory on the server — created automatically if it doesn't exist"
      >
        <Input
          value={form.database ?? ""}
          onChange={(e) => set({ database: e.target.value })}
          placeholder="/data/my-folder"
          autoFocus
        />
      </Field>
    );
  }

  if (provider.name === "s3") {
    return (
      <>
        <Field label="Bucket" hint="e.g. my-data-bucket">
          <Input
            value={form.database ?? ""}
            onChange={(e) => set({ database: e.target.value })}
            placeholder="my-data-bucket"
          />
        </Field>
        <Field
          label="Access Key ID"
          hint="Leave empty to use an IAM role or AWS_ACCESS_KEY_ID env var"
        >
          <Input
            value={form.username ?? ""}
            onChange={(e) => set({ username: e.target.value })}
            placeholder="AKIAIOSFODNN7EXAMPLE"
          />
        </Field>
        <SecretRefField
          label="Secret Access Key"
          hint="Env var name, keyring:NAME, or file:/path holding the secret key (optional if using IAM)"
          placeholder="AWS_SECRET_ACCESS_KEY"
          value={form.password_env ?? ""}
          onChange={(v) => set({ password_env: v })}
          suggestedName={`${form.name || "s3"}-secret-key`}
        />
        <div className="grid grid-cols-2 gap-3">
          <Field label="Region" hint="e.g. us-east-1 (optional)">
            <Input
              value={opts.region ?? ""}
              onChange={(e) => setOption("region", e.target.value)}
              placeholder="us-east-1"
            />
          </Field>
          <Field label="Endpoint URL" hint="For MinIO, R2, etc. (optional)">
            <Input
              value={form.host ?? ""}
              onChange={(e) => set({ host: e.target.value })}
              placeholder="http://localhost:9000"
            />
          </Field>
        </div>
      </>
    );
  }

  if (provider.name === "azure_blob") {
    return (
      <>
        <Field label="Container">
          <Input
            value={form.database ?? ""}
            onChange={(e) => set({ database: e.target.value })}
            placeholder="my-container"
          />
        </Field>
        <Field label="Storage account name">
          <Input
            value={form.username ?? ""}
            onChange={(e) => set({ username: e.target.value })}
            placeholder="mystorageaccount"
          />
        </Field>
        <SecretRefField
          label="Account key"
          hint="Env var name, keyring:NAME, or file:/path holding the account key"
          placeholder="AZURE_STORAGE_ACCOUNT_KEY"
          value={form.password_env ?? ""}
          onChange={(v) => set({ password_env: v })}
          suggestedName={`${form.name || "azure"}-account-key`}
        />
        <Field
          label="Endpoint URL"
          hint="For Azurite, sovereign/government clouds, etc. (optional — defaults to the public Azure endpoint for this account)"
        >
          <Input
            value={form.host ?? ""}
            onChange={(e) => set({ host: e.target.value })}
            placeholder="http://localhost:10000/devstoreaccount1"
          />
        </Field>
      </>
    );
  }

  if (provider.name === "gcs") {
    return (
      <>
        <Field label="Bucket">
          <Input
            value={form.database ?? ""}
            onChange={(e) => set({ database: e.target.value })}
            placeholder="my-gcs-bucket"
          />
        </Field>
        <Field
          label="Project ID"
          hint="Optional — uses the project from the service account if omitted"
        >
          <Input
            value={opts.project_id ?? ""}
            onChange={(e) => setOption("project_id", e.target.value)}
            placeholder="my-gcp-project"
          />
        </Field>
        {/* GCS holds a *path* to a JSON credentials file, not a secret value,
            so the keychain-save affordance doesn't apply here. */}
        <SecretRefField
          label="Service account key"
          hint="Env var name (or file: ref) holding the path to a service account JSON file. Leave empty for Application Default Credentials."
          placeholder="GOOGLE_APPLICATION_CREDENTIALS"
          value={form.password_env ?? ""}
          onChange={(v) => set({ password_env: v })}
          suggestedName={form.name}
          allowKeychain={false}
        />
      </>
    );
  }

  return null;
}
