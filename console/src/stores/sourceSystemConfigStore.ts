import { create } from "zustand";
import { sourceSystemConfigApi } from "../api/modules/sourceSystemConfig";
import type { EffectiveSourceSystemConfig } from "../api/types/sourceSystemConfig";

interface SourceSystemConfigState {
  config: EffectiveSourceSystemConfig | null;
  sourceId: string | null;
  loading: boolean;
  error: string | null;
  requestSeq: number;
  loadEffectiveConfig: (sourceId: string) => Promise<void>;
}

export const useSourceSystemConfigStore = create<SourceSystemConfigState>(
  (set, get) => ({
    config: null,
    sourceId: null,
    loading: false,
    error: null,
    requestSeq: 0,

    async loadEffectiveConfig(sourceId: string) {
      const nextSeq = get().requestSeq + 1;
      set({
        loading: true,
        error: null,
        requestSeq: nextSeq,
      });
      try {
        const config = await sourceSystemConfigApi.getEffective();
        if (get().requestSeq !== nextSeq) {
          return;
        }
        set({
          config,
          sourceId,
          loading: false,
          error: null,
        });
      } catch (error) {
        if (get().requestSeq !== nextSeq) {
          return;
        }
        set({
          loading: false,
          error: error instanceof Error ? error.message : String(error),
        });
      }
    },
  }),
);
