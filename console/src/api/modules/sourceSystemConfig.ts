import { request } from "../request";
import type {
  CurrentSourceSystemConfigResponse,
  CurrentSourceSystemConfigUpdateRequest,
  EffectiveSourceSystemConfig,
} from "../types/sourceSystemConfig";

export const sourceSystemConfigApi = {
  getEffective(): Promise<EffectiveSourceSystemConfig> {
    return request<EffectiveSourceSystemConfig>(
      "/source-system-config/effective",
    );
  },

  getCurrent(): Promise<CurrentSourceSystemConfigResponse> {
    return request<CurrentSourceSystemConfigResponse>(
      "/source-system-config/current",
    );
  },

  updateCurrent(
    payload: CurrentSourceSystemConfigUpdateRequest,
  ): Promise<CurrentSourceSystemConfigResponse> {
    return request<CurrentSourceSystemConfigResponse>(
      "/source-system-config/current",
      {
        method: "PUT",
        body: JSON.stringify(payload),
      },
    );
  },

  deleteCurrent(): Promise<{ deleted: boolean }> {
    return request<{ deleted: boolean }>(
      "/source-system-config/current",
      {
        method: "DELETE",
      },
    );
  },
};
