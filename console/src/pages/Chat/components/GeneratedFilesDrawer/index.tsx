import { useCallback, useEffect, useMemo, useState } from "react";
import { Button, Drawer, Empty, List, Select, Spin, Tooltip, Typography } from "antd";
import {
  SparkLocalFileLine,
  SparkRefreshLine,
  SparkSortLine,
} from "@agentscope-ai/icons";
import { getFileIcon } from "@/components/agentscope-chat/FilePreviewModal/fileUtils";
import { chatApi, type GeneratedFileItem } from "../../../../api/modules/chat";
import { toDisplayUrl } from "../../utils";
import ChatFilePreviewModal from "./ChatFilePreviewModal";
import styles from "./index.module.less";

type SortOrder = "desc" | "asc";
type FileSource = "all" | "generated" | "uploaded";

const sortOptions = [
  { label: "最新优先", value: "desc" },
  { label: "最早优先", value: "asc" },
];

const sourceOptions = [
  { label: "全部", value: "all" },
  { label: "生成", value: "generated" },
  { label: "上传", value: "uploaded" },
];

function formatFileSize(size: number) {
  if (!Number.isFinite(size) || size <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  let value = size;
  let unitIndex = 0;
  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024;
    unitIndex += 1;
  }
  return `${value.toFixed(unitIndex === 0 ? 0 : 1)} ${units[unitIndex]}`;
}

function formatModifiedTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "时间未知";
  return date.toLocaleString();
}

function getSourceLabel(source: GeneratedFileItem["source"]) {
  return source === "generated" ? "生成文件" : "上传文件";
}

function getPreviewTypeLabel(type: GeneratedFileItem["preview_type"]) {
  const labels: Record<GeneratedFileItem["preview_type"], string> = {
    image: "图片",
    video: "视频",
    audio: "音频",
    office: "文档",
    pdf: "PDF",
    markdown: "Markdown",
    text: "文本",
    html: "HTML",
    other: "文件",
  };
  return labels[type] || "文件";
}

function getDisplayName(file: GeneratedFileItem) {
  return file.display_name || file.name;
}

export default function GeneratedFilesDrawer() {
  const [open, setOpen] = useState(false);
  const [sortOrder, setSortOrder] = useState<SortOrder>("desc");
  const [source, setSource] = useState<FileSource>("all");
  const [files, setFiles] = useState<GeneratedFileItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [previewFile, setPreviewFile] = useState<GeneratedFileItem | null>(null);

  const loadFiles = useCallback(async () => {
    setLoading(true);
    try {
      const result = await chatApi.listGeneratedFiles(sortOrder, source);
      setFiles(result.files || []);
    } finally {
      setLoading(false);
    }
  }, [sortOrder, source]);

  useEffect(() => {
    if (open) {
      void loadFiles();
    }
  }, [loadFiles, open]);

  const previewUrl = useMemo(() => {
    if (!previewFile) return "";
    return toDisplayUrl(previewFile.file_url);
  }, [previewFile]);

  const handlePreview = useCallback((file: GeneratedFileItem) => {
    setPreviewFile(file);
  }, []);

  return (
    <>
      <Tooltip title="文件预览">
        <Button
          type="text"
          className={styles.triggerButton}
          icon={<SparkLocalFileLine />}
          onClick={() => setOpen(true)}
          aria-label="文件预览"
        />
      </Tooltip>

      <Drawer
        title={
          <div className={styles.drawerTitle}>
            <SparkLocalFileLine />
            <span>文件预览</span>
          </div>
        }
        open={open}
        onClose={() => setOpen(false)}
        width={520}
        className={styles.drawer}
        extra={
          <Tooltip title="刷新">
            <Button
              type="text"
              icon={<SparkRefreshLine />}
              onClick={() => void loadFiles()}
              aria-label="刷新聊天文件列表"
            />
          </Tooltip>
        }
      >
        <div className={styles.summary}>
          <div>
            <div className={styles.summaryTitle}>聊天相关文件</div>
            <div className={styles.summaryMeta}>
              共 {files.length} 个文件，点击条目可预览
            </div>
          </div>
        </div>

        <div className={styles.filterPanel}>
          <div className={styles.filterGroup}>
            <div className={styles.filterLabel}>文件来源</div>
            <Select
              className={styles.filterSelect}
              value={source}
              options={sourceOptions}
              onChange={(value) => setSource(value as FileSource)}
            />
          </div>
          <div className={styles.filterGroup}>
            <div className={styles.filterLabel}>
              <SparkSortLine />
              <span>时间排序</span>
            </div>
            <Select
              className={styles.filterSelect}
              value={sortOrder}
              options={sortOptions}
              onChange={(value) => setSortOrder(value as SortOrder)}
            />
          </div>
        </div>

        <Spin spinning={loading}>
          {files.length === 0 ? (
            <Empty
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              description="暂无聊天文件"
              className={styles.empty}
            />
          ) : (
            <List
              className={styles.fileList}
              dataSource={files}
              renderItem={(file) => {
                const displayName = getDisplayName(file);
                const { icon, color } = getFileIcon(displayName, 28);
                return (
                  <List.Item
                    className={styles.fileItem}
                    onClick={() => handlePreview(file)}
                    role="button"
                    tabIndex={0}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault();
                        handlePreview(file);
                      }
                    }}
                  >
                    <div className={styles.fileIcon} style={{ color }}>
                      {icon}
                    </div>
                    <div className={styles.fileMeta}>
                      <Typography.Text
                        className={styles.fileName}
                        ellipsis={{ tooltip: file.name }}
                      >
                        {displayName}
                      </Typography.Text>
                      <div className={styles.fileSubline}>
                        <span className={styles.sourceBadge}>
                          {getSourceLabel(file.source)}
                        </span>
                        <span className={styles.typeBadge}>
                          {getPreviewTypeLabel(file.preview_type)}
                        </span>
                        <span>{formatFileSize(file.size)}</span>
                      </div>
                      <div className={styles.fileTime}>
                        {formatModifiedTime(file.modified_at)}
                      </div>
                    </div>
                  </List.Item>
                );
              }}
            />
          )}
        </Spin>
      </Drawer>

      <ChatFilePreviewModal
        open={Boolean(previewFile)}
        onClose={() => setPreviewFile(null)}
        fileUrl={previewUrl}
        fileName={previewFile ? getDisplayName(previewFile) : ""}
        previewType={previewFile?.preview_type}
      />
    </>
  );
}
