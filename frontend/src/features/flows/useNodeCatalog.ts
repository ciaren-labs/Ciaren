import { useEffect, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { catalogApi } from "@/features/flows/api";
import { mergeNodeCatalog } from "@/lib/catalogMerge";
import { NODE_TYPES, setRuntimeNodeDefs, type NodeTypeDef } from "@/lib/nodeCatalog";

/**
 * The node catalog the editor renders, sourced from the backend
 * (`GET /api/catalog/nodes`, which includes plugin-contributed nodes) merged over
 * the static `NODE_TYPES`. While the request is in flight or if it fails, the
 * static list is used so the editor always works offline. As a side effect it
 * installs the merged set as the runtime overlay (`setRuntimeNodeDefs`) so other
 * catalog consumers (canvas drop, validation) resolve plugin nodes too.
 */
export function useNodeCatalog(): NodeTypeDef[] {
  const { data } = useQuery({
    queryKey: ["catalog", "nodes"],
    queryFn: catalogApi.nodes,
    staleTime: 5 * 60 * 1000,
  });

  const merged = useMemo(
    () => (data ? mergeNodeCatalog(NODE_TYPES, data) : NODE_TYPES),
    [data],
  );

  useEffect(() => {
    setRuntimeNodeDefs(merged);
  }, [merged]);

  return merged;
}
