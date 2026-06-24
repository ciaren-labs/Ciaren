import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { connectionsApi } from "@/lib/api";
import { queryKeys } from "@/lib/queryClient";
import type { ConnectionCreate, ConnectionUpdate } from "@/lib/types";

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
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.connections }),
  });
}

export function useUpdateConnection() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: ConnectionUpdate }) =>
      connectionsApi.update(id, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.connections }),
  });
}

export function useDeleteConnection() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => connectionsApi.remove(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.connections }),
  });
}

export function useTestConnection() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => connectionsApi.test(id),
    // Refresh the list so the "last tested" timestamp updates immediately.
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.connections }),
  });
}

export function useTestConnectionConfig() {
  return useMutation({
    mutationFn: (body: ConnectionCreate) => connectionsApi.testConfig(body),
  });
}

export function useConnectionObjects(id: string | null, enabled = true) {
  return useQuery({
    queryKey: id ? queryKeys.connectionObjects(id) : ["connections", "none", "objects"],
    queryFn: () => connectionsApi.objects(id as string),
    enabled: !!id && enabled,
  });
}
