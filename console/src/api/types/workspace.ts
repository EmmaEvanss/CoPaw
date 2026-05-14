export interface MdFileInfo {
  filename: string;
  path: string;
  size: number;
  created_time: string;
  modified_time: string;
}

export interface MdFileContent {
  content: string;
}

export interface MarkdownFile extends MdFileInfo {
  updated_at: number;
  enabled?: boolean;
}

export interface DailyMemoryFile extends MdFileInfo {
  date: string;
  updated_at: number;
}

// --- File broadcast types ---

export interface BroadcastFileTenantResult {
  tenant_id: string;
  success: boolean;
  bootstrapped: boolean;
  files_updated: string[];
  error?: string;
}

export interface BroadcastFilesResponse {
  results: BroadcastFileTenantResult[];
}
