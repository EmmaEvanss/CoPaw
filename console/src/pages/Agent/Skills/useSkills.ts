import { useState, useEffect, useCallback, useRef } from "react";
import { useAppMessage } from "../../../hooks/useAppMessage";
import api from "../../../api";
import type { SecurityScanErrorResponse } from "../../../api/modules/security";
import { invalidateSkillCache } from "../../../api/modules/skill";
import type { SkillSpec } from "../../../api/types";
import { useTranslation } from "react-i18next";
import { useAgentStore } from "../../../stores/agentStore";
import { parseErrorDetail } from "../../../utils/error";
import {
  handleScanError,
  checkScanWarnings as checkScanWarningsShared,
  showScanErrorModal,
} from "../../../utils/scanError";

export type SkillConflictDetail = {
  suggested_name?: string;
  conflicts?: {
    reason?: string;
    skill_name?: string;
    suggested_name?: string;
  }[];
};

export type SkillActionResult =
  | { success: true; name?: string; imported?: string[] }
  | { success: false; conflict?: SkillConflictDetail };

export function useSkills() {
  const { t } = useTranslation();
  const { selectedAgent } = useAgentStore();
  const [skills, setSkills] = useState<SkillSpec[]>([]);
  const [loading, setLoading] = useState(false);
  const [importing, setImporting] = useState(false);
  const importTaskIdRef = useRef<string | null>(null);
  const importCancelReasonRef = useRef<"manual" | "timeout" | null>(null);
  const { message } = useAppMessage();

  const handleError = useCallback(
    (error: unknown, defaultMsg: string): boolean => {
      if (handleScanError(error, t)) return true;
      const msg =
        error instanceof Error && error.message ? error.message : defaultMsg;
      console.error(defaultMsg, error);
      message.error(msg);
      return false;
    },
    [t],
  );

  const checkScanWarnings = useCallback(
    (skillName: string) =>
      checkScanWarningsShared(
        skillName,
        api.getBlockedHistory,
        api.getSkillScanner,
        t,
      ),
    [t],
  );

  const fetchSkills = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.listSkills(selectedAgent);
      setSkills(data || []);
    } catch (error) {
      console.error("Failed to load skills", error);
      message.error("Failed to load skills");
    } finally {
      setLoading(false);
    }
  }, [selectedAgent]);

  const hardRefresh = useCallback(async () => {
    setLoading(true);
    try {
      invalidateSkillCache({ agentId: selectedAgent });
      const data = await api.refreshSkills(selectedAgent);
      setSkills(data || []);
    } catch (error) {
      console.error("Failed to refresh skills", error);
      message.error("Failed to refresh skills");
    } finally {
      setLoading(false);
    }
  }, [selectedAgent]);

  // Invalidate cache when agent changes
  useEffect(() => {
    invalidateSkillCache({ agentId: selectedAgent });
    void fetchSkills();
  }, [selectedAgent, fetchSkills]);

  const importFromHub = async (
    input: string,
    targetName?: string,
  ): Promise<SkillActionResult> => {
    const text = (input || "").trim();
    if (!text) {
      message.warning("Please provide a hub skill URL");
      return { success: false };
    }
    if (!text.startsWith("http://") && !text.startsWith("https://")) {
      message.warning(
        "Please enter a valid URL starting with http:// or https://",
      );
      return { success: false };
    }
    const timeoutMs = 90_000;
    const pollMs = 1_000;
    const startedAt = Date.now();
    try {
      setImporting(true);
      importCancelReasonRef.current = null;
      const payload = {
        bundle_url: text,
        enable: true,
        overwrite: false,
        target_name: targetName,
      };
      const task = await api.startHubSkillInstall(payload);
      importTaskIdRef.current = task.task_id;

      while (importTaskIdRef.current) {
        const status = await api.getHubSkillInstallStatus(task.task_id);

        if (status.status === "completed" && status.result?.installed) {
          message.success(`Imported skill: ${status.result.name}`);
          invalidateSkillCache({ agentId: selectedAgent }); // Clear cache after mutation
          await fetchSkills();
          if (status.result.name) {
            await checkScanWarnings(status.result.name);
          }
          return { success: true, name: String(status.result.name || "") };
        }

        if (status.status === "failed") {
          if (
            Array.isArray(status.result?.conflicts) &&
            status.result.conflicts.length > 0
          ) {
            return {
              success: false,
              conflict: status.result as SkillConflictDetail,
            };
          }
          const hubResult = status.result as unknown as
            | SecurityScanErrorResponse
            | null
            | undefined;
          if (hubResult?.type === "security_scan_failed") {
            showScanErrorModal(hubResult, t);
            return { success: false };
          }
          throw new Error(status.error || "Import failed");
        }

        if (status.status === "cancelled") {
          message.warning(
            t(
              importCancelReasonRef.current === "timeout"
                ? "skills.importTimeout"
                : "skills.importCancelled",
            ),
          );
          return { success: false };
        }

        if (Date.now() - startedAt >= timeoutMs) {
          importCancelReasonRef.current = "timeout";
          await api.cancelHubSkillInstall(task.task_id);
        }

        await new Promise((resolve) => window.setTimeout(resolve, pollMs));
      }

      return { success: false };
    } catch (error) {
      handleError(error, "Import failed");
      return { success: false };
    } finally {
      importTaskIdRef.current = null;
      importCancelReasonRef.current = null;
      setImporting(false);
    }
  };

  const cancelImport = useCallback(() => {
    if (!importing) return;
    importCancelReasonRef.current = "manual";
    const taskId = importTaskIdRef.current;
    if (!taskId) return;
    void api.cancelHubSkillInstall(taskId);
  }, [importing]);

  return {
    skills,
    loading,
    importing,
    importFromHub,
    cancelImport,
    refreshSkills: fetchSkills,
    hardRefresh,
  };
}
