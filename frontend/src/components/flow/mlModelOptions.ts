import type { MlModelCatalogItem } from "@/features/models/types";

export function modelInstallWarning(item: MlModelCatalogItem | undefined): string | undefined {
  if (!item || item.available !== false) return undefined;
  const missing = item.missing ?? [];
  return item.warning ?? (missing.length ? `Missing dependency: ${missing.join(", ")}` : "Unavailable");
}

export function modelOptionLabel(label: string, item: MlModelCatalogItem | undefined): string {
  const warning = modelInstallWarning(item);
  if (!warning) return label;
  const missing = item?.missing?.length ? ` (${item.missing.join(", ")})` : "";
  return `⚠ ${label}${missing}`;
}
