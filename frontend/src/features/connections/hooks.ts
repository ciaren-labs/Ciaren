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
    staleTime: 5 * 60_000, // driver availability rarely changes at runtime
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
  return useMutation({
    mutationFn: (id: string) => connectionsApi.test(id),
  });
}

export function useTestConnectionConfig() {
  return useMutation({
    mutationFn: (body: ConnectionCreate) => connectionsApi.testConfig(body),
  });
}
