import { useMutation, useQuery } from "@tanstack/react-query";
import { transformationsApi } from "@/lib/api";
import { queryKeys } from "@/lib/queryClient";
import type { TransformationPreviewRequest } from "@/lib/types";

export function useTransformationTypes() {
  return useQuery({
    queryKey: queryKeys.transformations,
    queryFn: transformationsApi.list,
  });
}

export function useTransformationPreview() {
  return useMutation({
    mutationFn: (body: TransformationPreviewRequest) =>
      transformationsApi.preview(body),
  });
}
