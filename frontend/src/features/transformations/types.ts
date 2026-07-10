export interface TransformationPreviewRequest {
  type: string;
  dataset_id: string;
  config: Record<string, unknown>;
  limit?: number;
  profile?: boolean;
}
