import { request } from "../request";
import type { EnvPatchRequest, EnvVar } from "../types";

export const envApi = {
  listEnvs: () => request<EnvVar[]>("/envs"),

  /** Batch save – full replacement of all env vars. */
  saveEnvs: (envs: Record<string, string>) =>
    request<EnvVar[]>("/envs", {
      method: "PUT",
      body: JSON.stringify(envs),
    }),

  patchEnvs: (body: EnvPatchRequest) =>
    request<EnvVar[]>("/envs", {
      method: "PATCH",
      body: JSON.stringify(body),
    }),

  deleteEnv: (key: string) =>
    request<EnvVar[]>(`/envs/${encodeURIComponent(key)}`, {
      method: "DELETE",
    }),
};
