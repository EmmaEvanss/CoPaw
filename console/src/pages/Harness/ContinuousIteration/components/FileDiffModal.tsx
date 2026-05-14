import { useEffect, useState, useRef } from "react";
import { Modal, Button, Spin, Tag, Space, Typography, message } from "antd";
import {
  FileTextOutlined,
  RollbackOutlined,
} from "@ant-design/icons";
import { useTranslation } from "react-i18next";
import { diffLines, type Change } from "diff";
import { dreamLogsApi } from "../../../../api/modules/dreamLogs";
import type { DreamLogRecord, DiffResponse } from "../../../../api/types/dreamLogs";
import styles from "../index.module.less";

const { Text } = Typography;

interface FileDiffModalProps {
  visible: boolean;
  record: DreamLogRecord | null;
  filename: string;
  onClose: () => void;
  onRollback: () => void;
}

interface SideBySideRow {
  leftLineNum?: number;
  leftContent?: string;
  leftPrefix?: string;
  rightLineNum?: number;
  rightContent?: string;
  rightPrefix?: string;
  kind: "added" | "removed" | "unchanged";
}

function buildSideBySideRows(changes: Change[]): SideBySideRow[] {
  const rows: SideBySideRow[] = [];
  let leftLine = 1;
  let rightLine = 1;
  let pendingRemoved: { lineNum: number; content: string }[] = [];

  for (const change of changes) {
    const lines = change.value.replace(/\n$/, "").split("\n");

    if (change.added) {
      for (const content of lines) {
        if (pendingRemoved.length > 0) {
          const removed = pendingRemoved.shift()!;
          rows.push({
            leftLineNum: removed.lineNum,
            leftContent: removed.content,
            leftPrefix: "-",
            rightLineNum: rightLine,
            rightContent: content,
            rightPrefix: "+",
            kind: "removed",
          });
          rightLine++;
        } else {
          rows.push({
            rightLineNum: rightLine,
            rightContent: content,
            rightPrefix: "+",
            kind: "added",
          });
          rightLine++;
        }
      }
    } else if (change.removed) {
      for (const content of lines) {
        pendingRemoved.push({ lineNum: leftLine, content });
        leftLine++;
      }
    } else {
      // 先输出剩余的待匹配删除行
      for (const removed of pendingRemoved) {
        rows.push({
          leftLineNum: removed.lineNum,
          leftContent: removed.content,
          leftPrefix: "-",
          kind: "removed",
        });
      }
      pendingRemoved = [];

      for (const content of lines) {
        rows.push({
          leftLineNum: leftLine,
          leftContent: content,
          rightLineNum: rightLine,
          rightContent: content,
          kind: "unchanged",
        });
        leftLine++;
        rightLine++;
      }
    }
  }

  // 末尾剩余的删除行
  for (const removed of pendingRemoved) {
    rows.push({
      leftLineNum: removed.lineNum,
      leftContent: removed.content,
      leftPrefix: "-",
      kind: "removed",
    });
  }

  return rows;
}

export default function FileDiffModal({
  visible,
  record,
  filename,
  onClose,
  onRollback,
}: FileDiffModalProps) {
  const { t } = useTranslation();
  const [loading, setLoading] = useState(false);
  const [diffData, setDiffData] = useState<DiffResponse | null>(null);
  const [rolledBack, setRolledBack] = useState(false);
  const leftRef = useRef<HTMLDivElement>(null);
  const rightRef = useRef<HTMLDivElement>(null);
  const syncing = useRef(false);

  useEffect(() => {
    if (visible && record && filename) {
      setDiffData(null);
      setRolledBack(false);
      fetchDiff();
    }
  }, [visible, record, filename]);

  const fetchDiff = async () => {
    if (!record) return;
    setLoading(true);
    try {
      const data = await dreamLogsApi.diff(record.id, filename);
      setDiffData(data);
    } catch (error) {
      console.error("Failed to fetch diff:", error);
      message.error("Failed to load file comparison");
    } finally {
      setLoading(false);
    }
  };

  const formatSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes}B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)}MB`;
  };

  const handleScroll = (source: "left" | "right") => {
    if (syncing.current) return;
    syncing.current = true;
    if (source === "left" && leftRef.current && rightRef.current) {
      rightRef.current.scrollTop = leftRef.current.scrollTop;
    } else if (source === "right" && leftRef.current && rightRef.current) {
      leftRef.current.scrollTop = rightRef.current.scrollTop;
    }
    requestAnimationFrame(() => {
      syncing.current = false;
    });
  };

  const handleRollback = async () => {
    onRollback();
    setRolledBack(true);
  };

  if (!record) return null;

  const fileStats = record.file_stats[filename];
  const canRollback = !rolledBack;
  const sideBySideRows = diffData
    ? buildSideBySideRows(diffLines(diffData.content_before, diffData.content_after))
    : [];

  return (
    <Modal
      open={visible}
      onCancel={onClose}
      width={1200}
      footer={[
        <Button key="close" onClick={onClose}>
          {t("common.close")}
        </Button>,
        canRollback && (
          <Button
            key="rollback"
            type="primary"
            danger
            icon={<RollbackOutlined />}
            onClick={handleRollback}
          >
            {t("dreamLogs.rollback.single")}
          </Button>
        ),
      ]}
      title={
        <Space>
          <FileTextOutlined />
          {t("dreamLogs.diff.title")} - {filename}
        </Space>
      }
    >
      <Spin spinning={loading}>
        {diffData && (
          <>
            {/* File Stats Header */}
            <Space style={{ marginBottom: 16 }} size="small" wrap>
              <Tag color="blue">
                {t("dreamLogs.file.sizeBefore")}: {formatSize(diffData.size_before)}
              </Tag>
              <Text type="secondary">→</Text>
              <Tag color="green">
                {t("dreamLogs.file.sizeAfter")}: {formatSize(diffData.size_after)}
              </Tag>
              {diffData.size_saved > 0 && (
                <Tag color="success">
                  -{formatSize(diffData.size_saved)}
                </Tag>
              )}
              {diffData.size_saved < 0 && (
                <Tag color="error">
                  +{formatSize(Math.abs(diffData.size_saved))}
                </Tag>
              )}
              {fileStats && (
                <Tag>
                  {t("dreamLogs.file.linesRemoved")}: {fileStats.lines_removed}
                </Tag>
              )}
            </Space>

            {/* Side-by-side Diff */}
            <div className={styles.diffContainer}>
              {/* Left Panel — Before */}
              <div className={styles.diffPanel}>
                <div className={styles.diffHeader}>
                  <Text strong>{t("dreamLogs.diff.before")}</Text>
                  <Text type="secondary">
                    {diffData.content_before.split("\n").length} lines
                  </Text>
                </div>
                <div
                  className={styles.diffContent}
                  ref={leftRef}
                  onScroll={() => handleScroll("left")}
                >
                  {sideBySideRows.length === 0 ? (
                    <div className={styles.diffEmptyRow}>{t("dreamLogs.diff.noChanges")}</div>
                  ) : (
                    sideBySideRows.map((row, i) => (
                      <div
                        key={i}
                        className={`${styles.diffRow} ${
                          row.kind === "added"
                            ? styles.diffLineAdded
                            : row.kind === "removed"
                            ? styles.diffLineRemoved
                            : ""
                        }`}
                      >
                        <span className={styles.diffLineNum}>
                          {row.leftLineNum ?? ""}
                        </span>
                        <span className={styles.diffLinePrefix}>
                          {row.leftPrefix ?? " "}
                        </span>
                        <span>{row.leftContent ?? ""}</span>
                      </div>
                    ))
                  )}
                </div>
              </div>

              {/* Right Panel — After */}
              <div className={styles.diffPanel}>
                <div className={styles.diffHeader}>
                  <Text strong>{t("dreamLogs.diff.after")}</Text>
                  <Text type="secondary">
                    {diffData.content_after.split("\n").length} lines
                  </Text>
                </div>
                <div
                  className={styles.diffContent}
                  ref={rightRef}
                  onScroll={() => handleScroll("right")}
                >
                  {sideBySideRows.length === 0 ? (
                    <div className={styles.diffEmptyRow}>{t("dreamLogs.diff.noChanges")}</div>
                  ) : (
                    sideBySideRows.map((row, i) => (
                      <div
                        key={i}
                        className={`${styles.diffRow} ${
                          row.kind === "added"
                            ? styles.diffLineAdded
                            : row.kind === "removed"
                            ? styles.diffLineRemoved
                            : ""
                        }`}
                      >
                        <span className={styles.diffLineNum}>
                          {row.rightLineNum ?? ""}
                        </span>
                        <span className={styles.diffLinePrefix}>
                          {row.rightPrefix ?? " "}
                        </span>
                        <span>{row.rightContent ?? ""}</span>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>
          </>
        )}
      </Spin>
    </Modal>
  );
}
