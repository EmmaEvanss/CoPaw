import { useState } from "react";
import { Button, Input, Modal } from "@agentscope-ai/design";
import { Space } from "antd";
import { useTranslation } from "react-i18next";

export interface ConflictItem {
  key: string;
  label: string;
  suggested_name: string;
}

interface InternalItem extends ConflictItem {
  new_name: string;
}

export type ConflictResolveResult =
  | { action: "rename"; renameMap: Record<string, string> }
  | { action: "overwrite" }
  | null;

export function useConflictRenameModal(): {
  showConflictRenameModal: (
    items: ConflictItem[],
  ) => Promise<ConflictResolveResult>;
  conflictRenameModal: React.ReactNode;
} {
  const { t } = useTranslation();
  const [items, setItems] = useState<InternalItem[]>([]);
  const [resolver, setResolver] = useState<
    ((result: ConflictResolveResult) => void) | null
  >(null);

  const showConflictRenameModal = (
    incoming: ConflictItem[],
  ): Promise<ConflictResolveResult> =>
    new Promise((resolve) => {
      setItems(
        incoming.map((item) => ({ ...item, new_name: item.suggested_name })),
      );
      setResolver(() => resolve);
    });

  const handleRename = () => {
    const renameMap: Record<string, string> = {};
    for (const item of items) {
      if (item.new_name.trim()) {
        renameMap[item.key] = item.new_name.trim();
      }
    }
    resolver?.({ action: "rename", renameMap });
    setItems([]);
    setResolver(null);
  };

  const handleOverwrite = () => {
    resolver?.({ action: "overwrite" });
    setItems([]);
    setResolver(null);
  };

  const handleCancel = () => {
    resolver?.(null);
    setItems([]);
    setResolver(null);
  };

  const conflictRenameModal = (
    <Modal
      open={items.length > 0}
      title={t("skillPool.multiConflictTitle")}
      onCancel={handleCancel}
      zIndex={2100}
      footer={
        <Space>
          <Button onClick={handleCancel}>{t("common.cancel")}</Button>
          <Button type="primary" danger onClick={handleOverwrite}>
            {t("common.overwrite")}
          </Button>
          <Button type="primary" onClick={handleRename}>
            {t("common.rename")}
          </Button>
        </Space>
      }
    >
      <p>{t("skillPool.multiConflictDesc")}</p>
      {items.map((item, i) => (
        <div key={item.key} style={{ marginBottom: 12 }}>
          <div style={{ marginBottom: 4 }}>
            {t("skillPool.renameEntry", { name: item.label })}
          </div>
          <Input
            value={item.new_name}
            onChange={(e) => {
              const next = [...items];
              next[i] = { ...next[i], new_name: e.target.value };
              setItems(next);
            }}
          />
        </div>
      ))}
    </Modal>
  );

  return { showConflictRenameModal, conflictRenameModal };
}
