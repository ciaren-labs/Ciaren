import { request } from "@/lib/api/client";
import type { PreviewResponse } from "@/lib/types/shared";
import type { TransformationPreviewRequest } from "./types";

export const transformationsApi = {
  list: () => request<string[]>("/transformations"),
  preview: (body: TransformationPreviewRequest) =>
    request<PreviewResponse>("/transformations/preview", {
      method: "POST",
      body: JSON.stringify(body),
    }),
};
