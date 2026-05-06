/**
 * 市场 MCP 分发弹窗。
 *
 * 说明：
 * - 交互和提交流程对齐现有 MCP 菜单“分发到租户”
 * - 只替换数据来源：由市场条目发起分发
 */
import { useEffect, useMemo, useState } from "react";
import { Modal, message } from "antd";
import api from "../../api";
import { TenantTargetPicker } from "../../components/TenantTargetPicker";
import { marketMcpApi } from "../../api/modules/marketMcp";
import type { MarketMCPItem } from "../../api/types";

interface MCPDistributeModalProps {
  open: boolean;
  mcp: MarketMCPItem | null;
  sourceId: string;
  userId: string;
  userName: string;
  onClose: () => void;
  onSuccess: () => void;
}

export function MCPDistributeModal({
  open,
  mcp,
  sourceId,
  userId,
  userName,
  onClose,
  onSuccess,
}: MCPDistributeModalProps) {
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [tenantIds, setTenantIds] = useState<string[]>([]);
  const [selectedTenantIds, setSelectedTenantIds] = useState<string[]>([]);

  useEffect(() => {
    if (!open) return;
    setSelectedTenantIds([]);
    setLoading(true);
    void api
      .listMCPDistributionTenants()
      .then((result) => {
        setTenantIds(result.tenant_ids || []);
      })
      .catch((error) => {
        console.error("加载 MCP 分发租户失败:", error);
        message.error(error instanceof Error ? error.message : "加载租户失败");
      })
      .finally(() => {
        setLoading(false);
      });
  }, [open]);

  const sanitizedSelectedTenantIds = useMemo(
    () => Array.from(new Set(selectedTenantIds.filter(Boolean))),
    [selectedTenantIds],
  );

  const handleSubmit = async () => {
    if (!mcp || !sanitizedSelectedTenantIds.length) return;
    setSubmitting(true);
    try {
      const result = await marketMcpApi.distributeMCP(
        sourceId,
        mcp.item_id,
        userId,
        userName,
        {
          target_tenant_ids: sanitizedSelectedTenantIds,
          overwrite: true,
        },
      );

      const items = Array.isArray(result.results) ? result.results : [];
      const succeeded = items.filter((item) => item.success);
      const failed = items.filter((item) => !item.success);

      if (succeeded.length > 0) {
        const lines = succeeded.map((item) => {
          const suffix = item.bootstrapped ? " (已初始化)" : "";
          return `• ${item.tenant_id}${suffix}`;
        });
        message.success(`分发成功，共 ${succeeded.length} 个租户`);
        Modal.confirm({
          title: "分发结果",
          content: (
            <div style={{ display: "grid", gap: 8 }}>
              <div>以下租户分发成功：</div>
              <pre style={{ margin: 0, whiteSpace: "pre-wrap" }}>{lines.join("\n")}</pre>
              {failed.length > 0 ? <div>部分租户分发失败，请查看下方失败列表。</div> : null}
            </div>
          ),
          okText: "关闭",
          cancelButtonProps: { style: { display: "none" } },
        });
      }

      if (failed.length > 0) {
        const failureLines = failed.map(
          (item) => `• ${item.tenant_id}: ${item.error || "分发失败"}`,
        );
        if (succeeded.length === 0) {
          message.error("分发失败");
        }
        Modal.confirm({
          title: "部分租户分发失败",
          content: (
            <pre style={{ margin: 0, whiteSpace: "pre-wrap" }}>
              {failureLines.join("\n")}
            </pre>
          ),
          okText: "关闭",
          cancelButtonProps: { style: { display: "none" } },
        });
      }

      onSuccess();
      onClose();
    } catch (error) {
      console.error("分发市场 MCP 失败:", error);
      message.error(error instanceof Error ? error.message : "分发失败");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal
      open={open}
      title={`分发「${mcp?.name || ""}」`}
      onCancel={submitting ? undefined : onClose}
      onOk={handleSubmit}
      okText="分发"
      cancelText="取消"
      okButtonProps={{
        disabled: !sanitizedSelectedTenantIds.length,
        loading: submitting,
      }}
    >
      <div style={{ display: "grid", gap: 12 }}>
        <div style={{ color: "#666", fontSize: 12 }}>
          将当前市场 MCP 分发到目标租户的 default agent 中，行为与现有 MCP 分发到租户保持一致。
        </div>
        <div style={{ fontWeight: 500 }}>
          当前条目：{mcp?.name || "-"}（共选择 {sanitizedSelectedTenantIds.length} 个租户）
        </div>
        <div
          style={{
            display: "grid",
            gap: 4,
            padding: 12,
            borderRadius: 10,
            background: "#fff7e6",
            border: "1px solid #ffe7ba",
            color: "#ad6800",
            fontSize: 12,
          }}
        >
          <div>分发目标固定写入 default agent。</div>
          <div>如目标租户已存在同名 MCP，将按覆盖语义写入。</div>
        </div>
        {loading ? (
          <div>加载中…</div>
        ) : (
          <TenantTargetPicker
            tenantIds={tenantIds}
            selectedTenantIds={selectedTenantIds}
            onChange={setSelectedTenantIds}
          />
        )}
      </div>
    </Modal>
  );
}
