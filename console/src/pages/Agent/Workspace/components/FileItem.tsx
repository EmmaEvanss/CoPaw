import React from "react";
import { Button, Switch, Tooltip } from "@agentscope-ai/design";
import {
  CaretDownOutlined,
  CaretRightOutlined,
  HolderOutlined,
} from "@ant-design/icons";
import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import type { MarkdownFile, DailyMemoryFile } from "../../../../api/types";
import { formatFileSize, formatTimeAgo } from "./utils";
import { useTranslation } from "react-i18next";
import styles from "../index.module.less";

interface FileItemProps {
  file: MarkdownFile;
  selectedFile: MarkdownFile | null;
  expandedMemory: boolean;
  dailyMemories: DailyMemoryFile[];
  enabled?: boolean;
  selectable?: boolean;
  broadcastSelected?: boolean;
  onFileClick: (file: MarkdownFile) => void;
  onDailyMemoryClick: (daily: DailyMemoryFile) => void;
  onToggleEnabled: (filename: string) => void;
  onSelectToggle?: (filename: string) => void;
}

export const FileItem: React.FC<FileItemProps> = ({
  file,
  selectedFile,
  expandedMemory,
  dailyMemories,
  enabled = false,
  selectable = false,
  broadcastSelected = false,
  onFileClick,
  onDailyMemoryClick,
  onToggleEnabled,
  onSelectToggle,
}) => {
  const { t } = useTranslation();
  const isSelected = selectedFile?.filename === file.filename;
  const isMemoryFile = file.filename === "MEMORY.md";

  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({
    id: file.filename,
    disabled: !enabled,
  });

  const style: React.CSSProperties = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
    position: "relative",
    zIndex: isDragging ? 1 : undefined,
  };

  const handleToggleClick = (
    _checked: boolean,
    event:
      | React.MouseEvent<HTMLButtonElement>
      | React.KeyboardEvent<HTMLButtonElement>,
  ) => {
    event.stopPropagation();
    onToggleEnabled(file.filename);
  };

  return (
    <div ref={setNodeRef} style={style}>
      <div
        onClick={() => onFileClick(file)}
        className={`${styles.fileItem} ${isSelected ? styles.selected : ""} ${
          isDragging ? styles.dragging : ""
        } ${broadcastSelected ? styles.broadcastSelected : ""}`}
      >
        <div className={styles.fileItemHeader}>
          {enabled && (
            <div
              className={styles.dragHandle}
              {...attributes}
              {...listeners}
              onClick={(e) => e.stopPropagation()}
            >
              <HolderOutlined />
            </div>
          )}
          <div className={styles.fileInfo}>
            <div className={styles.fileItemName}>
              {enabled && <span className={styles.enabledBadge}>●</span>}
              {file.filename}
            </div>
            <div className={styles.fileItemMeta}>
              {formatFileSize(file.size)} · {formatTimeAgo(file.updated_at)}
            </div>
          </div>
          <div className={styles.fileItemActions}>
            <Tooltip title={t("workspace.systemPromptToggleTooltip")}>
              <Switch
                size="small"
                checked={enabled}
                onClick={handleToggleClick}
              />
            </Tooltip>
            {isMemoryFile && (
              <span className={styles.expandIcon}>
                {expandedMemory ? (
                  <CaretDownOutlined />
                ) : (
                  <CaretRightOutlined />
                )}
              </span>
            )}
            {selectable && onSelectToggle && (
              <Button
                size="small"
                className={`${styles.selectButton} ${
                  broadcastSelected ? styles.selectButtonActive : ""
                }`}
                onClick={(e) => {
                  e.stopPropagation();
                  onSelectToggle(file.filename);
                }}
              >
                {broadcastSelected
                  ? t("workspace.selected")
                  : t("workspace.select")}
              </Button>
            )}
          </div>
        </div>
      </div>

      {isMemoryFile && expandedMemory && (
        <div className={styles.dailyMemoryList}>
          {dailyMemories.map((daily) => {
            const isDailySelected =
              selectedFile?.filename === `${daily.date}.md`;
            return (
              <div
                key={daily.date}
                onClick={() => onDailyMemoryClick(daily)}
                className={`${styles.dailyMemoryItem} ${
                  isDailySelected ? styles.selected : ""
                }`}
              >
                <div className={styles.dailyMemoryName}>{daily.date}.md</div>
                <div className={styles.dailyMemoryMeta}>
                  {formatFileSize(daily.size)} ·{" "}
                  {formatTimeAgo(daily.updated_at)}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
