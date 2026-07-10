import { request } from "@/lib/api/client";
import type { AppSetting } from "./types";

export const settingsApi = {
  list: () => request<AppSetting[]>("/settings"),
  update: (key: string, value: number | string) =>
    request<AppSetting>(`/settings/${encodeURIComponent(key)}`, {
      method: "PUT",
      body: JSON.stringify({ value }),
    }),
  reset: (key: string) =>
    request<AppSetting>(`/settings/${encodeURIComponent(key)}`, { method: "DELETE" }),
};
