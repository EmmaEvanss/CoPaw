import { request } from "../request";
import { mergeHeaders } from "../mergeHeaders";

export interface MySkill {
  skill_name: string;
  source: string;
  description: string;
  version: string | null;
  received_version: string | null;
  distributed_by: string | null;
  is_received: boolean;
  has_update: boolean;
  enabled: boolean;
  category?: string;
  creator_name?: string;
}

export interface FileTreeNode {
  name: string;
  type: "file" | "directory";
  path: string;
  children?: FileTreeNode[];
}

export interface FileContentResponse {
  content: string;
  file_type: string;
}

export interface BatchOperationResponse {
  results: Record<string, { success: boolean; reason?: string }>;
  success_count: number;
  failed_count: number;
}

export const mySkillsApi = {
  getCreatedSkills: async (): Promise<MySkill[]> => {
    const opts = mergeHeaders();
    const all = await request<MySkill[]>("/market/skills/mine", opts);
    return all.filter((s) => !s.is_received);
  },

  getReceivedSkills: async (): Promise<MySkill[]> => {
    const opts = mergeHeaders();
    const all = await request<MySkill[]>("/market/skills/received", opts);
    return all.filter((s) => s.is_received);
  },

  listSkillFiles: async (skillName: string): Promise<FileTreeNode[]> => {
    const opts = mergeHeaders();
    return request<FileTreeNode[]>(
      `/market/skills/mine/${skillName}/files`,
      opts
    );
  },

  readSkillFile: async (
    skillName: string,
    filePath: string
  ): Promise<FileContentResponse> => {
    const opts = mergeHeaders();
    return request<FileContentResponse>(
      `/market/skills/mine/${skillName}/files/${filePath}`,
      opts
    );
  },

  saveSkillFile: async (
    skillName: string,
    filePath: string,
    content: string
  ): Promise<void> => {
    const opts: RequestInit = {
      method: "PUT",
      ...(mergeHeaders({
        "Content-Type": "application/json",
      })),
      body: JSON.stringify({ content }),
    };
    await request<void>(`/market/skills/mine/${skillName}/files/${filePath}`, opts);
  },

  deleteSkill: async (skillName: string): Promise<void> => {
    const opts: RequestInit = {
      method: "DELETE",
      ...mergeHeaders(),
    };
    await request<void>(`/market/skills/mine/${skillName}`, opts);
  },

  enableSkill: async (skillName: string): Promise<void> => {
    const opts: RequestInit = {
      method: "POST",
      ...mergeHeaders(),
    };
    await request<void>(`/market/skills/mine/${skillName}/enable`, opts);
  },

  disableSkill: async (skillName: string): Promise<void> => {
    const opts: RequestInit = {
      method: "POST",
      ...mergeHeaders(),
    };
    await request<void>(`/market/skills/mine/${skillName}/disable`, opts);
  },

  batchDeleteSkills: async (
    skillNames: string[]
  ): Promise<BatchOperationResponse> => {
    const opts: RequestInit = {
      method: "POST",
      ...(mergeHeaders({
        "Content-Type": "application/json",
      })),
      body: JSON.stringify({ skills: skillNames }),
    };
    return request<BatchOperationResponse>(`/market/skills/mine/batch-delete`, opts);
  },

  batchEnableSkills: async (
    skillNames: string[]
  ): Promise<BatchOperationResponse> => {
    const opts: RequestInit = {
      method: "POST",
      ...(mergeHeaders({
        "Content-Type": "application/json",
      })),
      body: JSON.stringify({ skills: skillNames }),
    };
    return request<BatchOperationResponse>(`/market/skills/mine/batch-enable`, opts);
  },

  batchDisableSkills: async (
    skillNames: string[]
  ): Promise<BatchOperationResponse> => {
    const opts: RequestInit = {
      method: "POST",
      ...(mergeHeaders({
        "Content-Type": "application/json",
      })),
      body: JSON.stringify({ skills: skillNames }),
    };
    return request<BatchOperationResponse>(`/market/skills/mine/batch-disable`, opts);
  },
};
