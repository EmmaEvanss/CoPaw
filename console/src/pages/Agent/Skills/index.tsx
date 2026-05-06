import { useEffect, useState } from "react";
import { Button, Modal, Tooltip } from "@agentscope-ai/design";
import {
  DownloadOutlined,
  ImportOutlined,
  ReloadOutlined,
  SwapOutlined,
} from "@ant-design/icons";
import type { PoolSkillSpec } from "../../../api/types";
import {
  SkillCard,
  ImportHubModal,
  PoolTransferModal,
  useConflictRenameModal,
} from "./components";
import { useSkills, type SkillConflictDetail } from "./useSkills";
import { useTranslation } from "react-i18next";
import { useAgentStore } from "../../../stores/agentStore";
import { useAppMessage } from "../../../hooks/useAppMessage";
import api from "../../../api";
import { invalidateSkillCache } from "../../../api/modules/skill";
import { parseErrorDetail } from "../../../utils/error";
import { PageHeader } from "@/components/PageHeader";
import styles from "./index.module.less";

function SkillsPage() {
  const { t } = useTranslation();
  const { message } = useAppMessage();
  const { selectedAgent } = useAgentStore();
  const {
    skills,
    loading,
    importing,
    importFromHub,
    cancelImport,
    refreshSkills: fetchSkills,
    hardRefresh,
  } = useSkills();
  const [importModalOpen, setImportModalOpen] = useState(false);
  const [hoverKey, setHoverKey] = useState<string | null>(null);
  const [poolSkills, setPoolSkills] = useState<PoolSkillSpec[]>([]);
  const [poolModal, setPoolModal] = useState<"download" | null>(null);
  const { showConflictRenameModal, conflictRenameModal } =
    useConflictRenameModal();

  // Only fetch pool skills when pool modal is opened, not on page load
  useEffect(() => {
    if (poolModal === "download") {
      void api
        .listSkillPoolSkills()
        .then(setPoolSkills)
        .catch(() => undefined);
    }
  }, [poolModal]);

  const closePoolModal = () => {
    setPoolModal(null);
  };

  const closeImportModal = () => {
    if (importing) return;
    setImportModalOpen(false);
  };

  const handleConfirmImport = async (url: string, targetName?: string) => {
    const result = await importFromHub(url, targetName);
    if (result.success) {
      closeImportModal();
    } else {
      const detail = (
        result as { success: false; conflict?: SkillConflictDetail }
      ).conflict;
      if (detail) {
        const suggested =
          detail?.suggested_name || detail?.conflicts?.[0]?.suggested_name;
        if (suggested) {
          const skillName = detail?.conflicts?.[0]?.skill_name || "";
          const renameMap = await showConflictRenameModal([
            {
              key: skillName,
              label: skillName,
              suggested_name: String(suggested),
            },
          ]);
          if (renameMap) {
            const newName = Object.values(renameMap)[0];
            if (newName) {
              await handleConfirmImport(url, newName);
            }
          }
        }
      }
    }
  };

  const handleDownloadFromPool = async (
    poolSkillNames: string[],
    overwrite?: boolean,
  ) => {
    if (poolSkillNames.length === 0) return;
    try {
      for (const skillName of poolSkillNames) {
        let targetName: string | undefined;
        let shouldOverwrite = overwrite;
        while (true) {
          try {
            await api.downloadSkillPoolSkill({
              skill_name: skillName,
              targets: [
                {
                  workspace_id: selectedAgent,
                  target_name: targetName,
                },
              ],
              overwrite: shouldOverwrite,
            });
            break;
          } catch (error) {
            const detail = parseErrorDetail(error);
            const conflict = detail?.conflicts?.[0];
            if (conflict?.reason === "builtin_upgrade") {
              const confirmed = await new Promise<boolean>((resolve) => {
                Modal.confirm({
                  title: t("skills.builtinUpgradeTitle"),
                  content: t("skills.builtinUpgradeContent", {
                    name: conflict.skill_name || skillName,
                  }),
                  onOk: () => resolve(true),
                  onCancel: () => resolve(false),
                });
              });
              if (!confirmed) return;
              shouldOverwrite = true;
              continue;
            }
            if (!conflict?.suggested_name) throw error;
            const renameMap = await showConflictRenameModal([
              {
                key: skillName,
                label: skillName,
                suggested_name: conflict.suggested_name,
              },
            ]);
            if (!renameMap) return;
            targetName = Object.values(renameMap)[0] || undefined;
          }
        }
      }
      message.success(t("skills.downloadedToWorkspace"));
      closePoolModal();
      invalidateSkillCache({ agentId: selectedAgent, pool: true }); // Clear current agent and pool cache
      await fetchSkills();
    } catch (error) {
      message.error(
        error instanceof Error
          ? error.message
          : t("common.download") + " failed",
      );
    }
  };

  return (
    <div className={styles.skillsPage}>
      <PageHeader
        items={[{ title: t("nav.agent") }, { title: t("skills.title") }]}
        extra={
          <div className={styles.headerRight}>
            <div className={styles.headerActionsLeft}>
              <Tooltip title={t("skills.refreshHint")}>
                <Button
                  type="default"
                  icon={<ReloadOutlined spin={loading} />}
                  onClick={hardRefresh}
                  disabled={loading}
                />
              </Tooltip>
              <Tooltip title={t("skills.downloadFromPoolHint")}>
                <Button
                  type="default"
                  className={styles.primaryTransferButton}
                  onClick={() => setPoolModal("download")}
                  icon={<DownloadOutlined />}
                >
                  {t("skills.downloadFromPool")}
                </Button>
              </Tooltip>
            </div>
            <div className={styles.headerActionsRight}>
              <Tooltip title={t("skills.importHubHint")}>
                <Button
                  type="default"
                  className={styles.creationActionButton}
                  onClick={() => setImportModalOpen(true)}
                  icon={<ImportOutlined />}
                >
                  {t("skills.importHub")}
                </Button>
              </Tooltip>
              <Tooltip title={t("skills.mySkillsHint")}>
                <Button
                  type="primary"
                  className={styles.primaryActionButton}
                  onClick={() => {
                    window.open("/skills-management", "_blank");
                  }}
                  icon={<SwapOutlined />}
                >
                  {t("skills.mySkills")}
                </Button>
              </Tooltip>
            </div>
          </div>
        }
      />

      <ImportHubModal
        open={importModalOpen}
        importing={importing}
        onCancel={closeImportModal}
        onConfirm={handleConfirmImport}
        cancelImport={cancelImport}
        hint="External hub import is separate from the local Skill Pool."
      />

      {loading ? (
        <div className={styles.loading}>
          <span className={styles.loadingText}>{t("common.loading")}</span>
        </div>
      ) : skills.length === 0 ? (
        <div className={styles.emptyState}>
          <div className={styles.emptyStateBadge}>
            {t("skills.emptyStateBadge")}
          </div>
          <h2 className={styles.emptyStateTitle}>
            {t("skills.emptyStateTitle")}
          </h2>
          <p className={styles.emptyStateText}>{t("skills.emptyStateText")}</p>
          <div className={styles.emptyStateActions}>
            <Button
              type="default"
              className={styles.primaryTransferButton}
              onClick={() => setPoolModal("download")}
              icon={<DownloadOutlined />}
            >
              {t("skills.emptyStateDownload")}
            </Button>
          </div>
        </div>
      ) : (
        <div className={styles.skillsGrid}>
          {skills
            .slice()
            .sort((a, b) => {
              if (a.enabled && !b.enabled) return -1;
              if (!a.enabled && b.enabled) return 1;
              return a.name.localeCompare(b.name);
            })
            .map((skill) => (
              <SkillCard
                key={skill.name}
                skill={skill}
                isHover={hoverKey === skill.name}
                onClick={() => {
                  // Read-only mode: no action on click
                }}
                onMouseEnter={() => setHoverKey(skill.name)}
                onMouseLeave={() => setHoverKey(null)}
                readOnly={true}
              />
            ))}
        </div>
      )}

      <PoolTransferModal
        mode={poolModal}
        poolSkills={poolSkills}
        onCancel={closePoolModal}
        onDownload={handleDownloadFromPool}
      />

      {conflictRenameModal}
    </div>
  );
}

export default SkillsPage;