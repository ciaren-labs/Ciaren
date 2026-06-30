import type { MlModelCatalogItem } from "@/lib/types";

export function modelInstallWarning(item: MlModelCatalogItem | undefined): string | undefined {
  if (!item || item.available !== false) return undefined;
  return item.warning ?? `Missing dependency: ${item.missing.join(", ")}`;
}

export function modelOptionLabel(label: string, item: MlModelCatalogItem | undefined): string {
  const warning = modelInstallWarning(item);
  if (!warning) return label;
  const missing = item?.missing.length ? ` (${item.missing.join(", ")})` : "";
  return `⚠ ${label}${missing}`;
}
