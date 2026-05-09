import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Image, Modal, Spin, Tooltip, message } from "antd";
import { FullscreenOutlined } from "@ant-design/icons";
import {
  SparkCopyLine,
  SparkDownloadLine,
  SparkFalseLine,
  SparkTrueLine,
} from "@agentscope-ai/icons";
import { IconButton } from "@agentscope-ai/design";
import { buildAuthHeaders } from "@/api/authHeaders";
import { Markdown } from "@/components/agentscope-chat";
import {
  getContentType,
  getFileIcon,
} from "@/components/agentscope-chat/FilePreviewModal/fileUtils";
import type { GeneratedFileItem } from "../../../../api/modules/chat";

type PreviewType = GeneratedFileItem["preview_type"];

interface ChatFilePreviewModalProps {
  open: boolean;
  onClose: () => void;
  fileUrl: string;
  fileName: string;
  previewType?: PreviewType;
}

const TEXT_MAX_LENGTH = 50000;
const BLOB_PREVIEW_TYPES: PreviewType[] = ["image", "video", "audio", "pdf", "html"];
const FULLSCREEN_PREVIEW_TYPES: PreviewType[] = [
  ...BLOB_PREVIEW_TYPES,
  "markdown",
  "text",
];

const textPreviewStyle: React.CSSProperties = {
  width: "100%",
  maxHeight: "400px",
  overflow: "auto",
  backgroundColor: "#f5f5f5",
  borderRadius: "8px",
  padding: "12px",
  fontFamily: "monospace",
  fontSize: "12px",
  lineHeight: "1.5",
  whiteSpace: "pre-wrap",
  wordBreak: "break-all",
};

function ChatFilePreviewModal(props: ChatFilePreviewModalProps) {
  const { open, onClose, fileUrl, fileName, previewType = "other" } = props;
  const [copied, setCopied] = useState(false);
  const [fullscreen, setFullscreen] = useState(false);
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [blobLoading, setBlobLoading] = useState(false);
  const [blobError, setBlobError] = useState<string | null>(null);
  const [textContent, setTextContent] = useState<string | null>(null);
  const [textLoading, setTextLoading] = useState(false);
  const [textError, setTextError] = useState<string | null>(null);

  const { icon, color } = useMemo(() => getFileIcon(fileName, 48), [fileName]);
  const previewUrl = blobUrl || fileUrl;
  const previewHeight = fullscreen ? "85vh" : "500px";

  useEffect(() => {
    if (!open || !BLOB_PREVIEW_TYPES.includes(previewType) || !fileUrl) {
      setBlobUrl(null);
      setBlobLoading(false);
      setBlobError(null);
      return;
    }

    let objectUrl: string | null = null;
    let cancelled = false;

    setBlobUrl(null);
    setBlobLoading(true);
    setBlobError(null);

    fetch(fileUrl, { headers: buildAuthHeaders() })
      .then((res) => {
        if (!res.ok) throw new Error("加载失败");
        return res.blob();
      })
      .then((blob) => {
        if (cancelled) return;

        const normalizedBlob = new Blob([blob], {
          type: getContentType(fileName),
        });
        objectUrl = URL.createObjectURL(normalizedBlob);
        setBlobUrl(objectUrl);
      })
      .catch(() => {
        if (!cancelled) {
          setBlobError("文件暂时无法预览，请尝试下载查看");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setBlobLoading(false);
        }
      });

    return () => {
      cancelled = true;
      if (objectUrl) {
        URL.revokeObjectURL(objectUrl);
      }
    };
  }, [fileName, fileUrl, open, previewType]);

  useEffect(() => {
    if (!open || (previewType !== "text" && previewType !== "markdown") || !fileUrl) {
      setTextContent(null);
      setTextLoading(false);
      setTextError(null);
      return;
    }

    let cancelled = false;

    setTextContent(null);
    setTextLoading(true);
    setTextError(null);

    fetch(fileUrl, { headers: buildAuthHeaders() })
      .then((res) => {
        if (!res.ok) throw new Error("加载失败");
        return res.text();
      })
      .then((text) => {
        if (cancelled) return;

        setTextContent(
          text.length > TEXT_MAX_LENGTH
            ? `${text.slice(0, TEXT_MAX_LENGTH)}\n\n... (内容过长，已截断)`
            : text,
        );
      })
      .catch(() => {
        if (!cancelled) {
          setTextError("文件暂时无法预览，请尝试下载查看");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setTextLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [fileUrl, open, previewType]);

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(fileUrl);
      message.success("链接已复制");
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      message.error("复制失败");
    }
  }, [fileUrl]);

  const handleDownload = useCallback(async () => {
    try {
      const res = await fetch(fileUrl, { headers: buildAuthHeaders() });
      if (!res.ok) throw new Error("下载失败");

      const blob = await res.blob();
      const objectUrl = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = objectUrl;
      link.download = fileName;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(objectUrl);
    } catch {
      message.error("下载失败");
    }
  }, [fileName, fileUrl]);

  const renderPreviewError = useCallback(
    (errorText: string | null) => (
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", padding: "24px" }}>
        <div style={{ color: "#8c8c8c", marginBottom: "16px", fontSize: "14px" }}>
          {errorText || "文件暂时无法预览，请尝试下载查看"}
        </div>
        <IconButton icon={<SparkDownloadLine />} onClick={handleDownload}>
          下载文件查看
        </IconButton>
      </div>
    ),
    [handleDownload],
  );

  const renderPreviewContent = useMemo(() => {
    if (blobLoading) {
      return <Spin tip="加载中..." />;
    }

    if (blobError) {
      return renderPreviewError(blobError);
    }

    if (previewType === "image") {
      return (
        <div style={{ display: "flex", alignItems: "center", justifyContent: "center" }}>
          <Image
            src={previewUrl}
            alt={fileName}
            style={{ maxWidth: "100%", maxHeight: previewHeight, objectFit: "contain" }}
          />
        </div>
      );
    }

    if (previewType === "video") {
      return (
        <div style={{ display: "flex", alignItems: "center", justifyContent: "center" }}>
          <video controls style={{ maxWidth: "100%", maxHeight: previewHeight }} src={previewUrl}>
            <source src={previewUrl} />
          </video>
        </div>
      );
    }

    if (previewType === "audio") {
      return (
        <div style={{ display: "flex", alignItems: "center", justifyContent: "center", padding: "20px 0" }}>
          <audio controls style={{ width: "100%" }} src={previewUrl}>
            <source src={previewUrl} />
          </audio>
        </div>
      );
    }

    if (previewType === "pdf" || previewType === "html") {
      return (
        <div style={{ width: "100%", height: previewHeight }}>
          <iframe
            src={previewUrl}
            style={{ width: "100%", height: "100%", border: "none" }}
            title="File Preview"
            sandbox={previewType === "html" ? "allow-scripts allow-same-origin" : undefined}
          />
        </div>
      );
    }

    if (previewType === "markdown") {
      if (textLoading) return <Spin tip="加载中..." />;
      if (textError) return renderPreviewError(textError);
      if (textContent) {
        return (
          <div style={{ width: "100%", maxHeight: previewHeight, overflow: "auto", padding: "12px" }}>
            <Markdown content={textContent} allowHtml />
          </div>
        );
      }
      return null;
    }

    if (previewType === "text") {
      if (textLoading) return <Spin tip="加载中..." />;
      if (textError) return renderPreviewError(textError);
      if (textContent) {
        return (
          <div style={{ ...textPreviewStyle, maxHeight: previewHeight }}>
            <code>{textContent}</code>
          </div>
        );
      }
      return null;
    }

    return (
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: "24px", textAlign: "center" }}>
        <div style={{ marginBottom: "16px", color }}>{icon}</div>
        <div style={{ fontSize: "16px", fontWeight: 500, marginBottom: "8px", maxWidth: "300px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {fileName}
        </div>
        <div style={{ fontSize: "12px", color: "#8c8c8c", marginBottom: "16px" }}>
          该文件类型不支持预览
        </div>
        <IconButton icon={<SparkDownloadLine />} onClick={handleDownload}>
          下载文件
        </IconButton>
      </div>
    );
  }, [
    blobError,
    blobLoading,
    color,
    fileName,
    handleDownload,
    icon,
    previewHeight,
    previewType,
    previewUrl,
    renderPreviewError,
    textContent,
    textError,
    textLoading,
  ]);

  const headerActions = useMemo(() => {
    const actions = [
      <Tooltip key="copy" title="复制链接">
        <IconButton
          size="small"
          icon={copied ? <SparkTrueLine style={{ color: "#52c41a" }} /> : <SparkCopyLine />}
          onClick={handleCopy}
          bordered={false}
        />
      </Tooltip>,
      <Tooltip key="download" title="下载文件">
        <IconButton
          size="small"
          icon={<SparkDownloadLine />}
          onClick={handleDownload}
          bordered={false}
        />
      </Tooltip>,
    ];

    if (FULLSCREEN_PREVIEW_TYPES.includes(previewType)) {
      actions.unshift(
        <Tooltip key="fullscreen" title={fullscreen ? "退出全屏" : "全屏预览"}>
          <IconButton
            size="small"
            icon={<FullscreenOutlined />}
            onClick={() => setFullscreen((prev) => !prev)}
            bordered={false}
          />
        </Tooltip>,
      );
    }

    return actions;
  }, [copied, fullscreen, handleCopy, handleDownload, previewType]);

  return (
    <Modal
      open={open}
      onCancel={onClose}
      footer={null}
      width={fullscreen ? "95vw" : 800}
      centered
      closeIcon={
        <IconButton
          size="small"
          icon={<SparkFalseLine />}
          bordered={false}
        />
      }
      title={
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", width: "100%" }}>
          <span style={{ fontSize: "14px", fontWeight: 500, maxWidth: fullscreen ? "60vw" : "400px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {fileName}
          </span>
          <div style={{ display: "flex", alignItems: "center", gap: "12px", marginRight: "32px" }}>
            {headerActions}
          </div>
        </div>
      }
      styles={{
        content: { padding: "16px 24px" },
        body: { padding: "16px 0" },
      }}
    >
      <div style={{ display: "flex", justifyContent: "center", minHeight: fullscreen ? "85vh" : "200px" }}>
        {renderPreviewContent}
      </div>
    </Modal>
  );
}

export default ChatFilePreviewModal;
