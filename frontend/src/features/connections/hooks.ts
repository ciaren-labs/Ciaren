import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, connectionsApi } from "@/lib/api";
import { queryKeys } from "@/lib/queryClient";
import { toast } from "@/stores/toastStore";
import type { ConnectionCreate, ConnectionUpdate, KeyringSecretWrite } from "@/lib/types";

export function useConnections() {
  return useQuery({
    queryKey: queryKeys.connections,
    queryFn: () => connectionsApi.list(),
  });
}

export function useConnectionProviders() {
  return useQuery({
    queryKey: queryKeys.connectionProviders,
    queryFn: () => connectionsApi.providers(),
    // Short stale time so that installing a driver (no restart needed —
    // find_spec is non-caching and connectors use lazy imports) is picked up
    // quickly, especially after the user clicks "Recheck drivers".
    staleTime: 30_000,
  });
}

export function useConnectionTables(id: string | null, enabled = true) {
  return useQuery({
    queryKey: id ? queryKeys.connectionTables(id) : ["connections", "none", "tables"],
    queryFn: () => connectionsApi.tables(id as string),
    enabled: !!id && enabled,
  });
}

export function useCreateConnection() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: ConnectionCreate) => connectionsApi.create(body),
    // The connection form dialog renders failures inline.
    meta: { suppressErrorToast: true },
    onSuccess: (connection) => {
      qc.invalidateQueries({ queryKey: queryKeys.connections });
      toast.success(`Connection "${connection.name}" created`);
    },
  });
}

export function useUpdateConnection() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: ConnectionUpdate }) =>
      connectionsApi.update(id, body),
    // The connection form dialog renders failures inline.
    meta: { suppressErrorToast: true },
    onSuccess: (connection) => {
      qc.invalidateQueries({ queryKey: queryKeys.connections });
      toast.success(`Connection "${connection.name}" updated`);
    },
  });
}

export function useDeleteConnection() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, force }: { id: string; force?: boolean }) => connectionsApi.remove(id, force),
    // A 409 ("still used by flows") is handled by the caller with a confirm →
    // force retry, so it must not also fire the global error toast.
    meta: { suppressErrorToast: true },
    onError: (err) => {
      if (!(err instanceof ApiError && err.status === 409)) {
        toast.error("Couldn't delete the connection");
      }
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.connections });
      toast.success("Connection deleted");
    },
  });
}

export function useTestConnection() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => connectionsApi.test(id),
    // Test results (pass and fail) are rendered inline next to the button.
    meta: { suppressErrorToast: true },
    // Refresh the list so the "last tested" timestamp updates immediately.
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.connections }),
  });
}

export function useTestConnectionConfig() {
  return useMutation({
    mutationFn: (body: ConnectionCreate) => connectionsApi.testConfig(body),
    // Test results (pass and fail) are rendered inline in the form dialog.
    meta: { suppressErrorToast: true },
  });
}

export function useConnectionObjects(id: string | null, prefix?: string, enabled = true) {
  return useQuery({
    // The key includes the prefix so browsing into a different folder can't read
    // a sibling prefix's cached listing — the API already scopes objects by prefix.
    queryKey: id ? queryKeys.connectionObjects(id, prefix) : ["connections", "none", "objects"],
    queryFn: () => connectionsApi.objects(id as string, prefix),
    enabled: !!id && enabled,
  });
}

/** Whether this host has a usable OS keychain, so the form can offer or hide
 * the "save to keychain" action. Cached for the session — it can't change. */
export function useKeyringAvailability() {
  return useQuery({
    queryKey: ["connections", "keyring", "availability"],
    queryFn: () => connectionsApi.keyringStatus(),
    staleTime: Infinity,
  });
}

/** Store a secret in the OS keychain from the connection form. A 409 (name
 * already taken) is surfaced to the caller to confirm an overwrite; the value
 * is never cached, logged, or echoed back. */
export function useStoreKeyringSecret() {
  return useMutation({
    mutationFn: (body: KeyringSecretWrite) => connectionsApi.storeKeyringSecret(body),
    meta: { suppressErrorToast: true },
  });
}
