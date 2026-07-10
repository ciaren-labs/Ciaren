import { request } from "@/lib/api/client";
import type { Project, ProjectCreate, ProjectUpdate } from "./types";

export const projectsApi = {
  list: () => request<Project[]>("/projects"),
  get: (id: string) => request<Project>(`/projects/${id}`),
  create: (body: ProjectCreate) =>
    request<Project>("/projects", { method: "POST", body: JSON.stringify(body) }),
  update: (id: string, body: ProjectUpdate) =>
    request<Project>(`/projects/${id}`, { method: "PUT", body: JSON.stringify(body) }),
  remove: (id: string) => request<void>(`/projects/${id}`, { method: "DELETE" }),
};
