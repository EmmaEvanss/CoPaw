/**
 * 通用分发目标弹窗。
 *
 * 支持技能和 MCP 分发，统一交互和布局。
 */
import { useEffect, useMemo, useState } from "react";
import { Modal, message, Radio, Select, Spin, Button } from "antd";
import { CheckOutlined } from "@ant-design/icons";
import api from "../../api";
import { marketApi, DistributeRequest } from "../../api/modules/market";
import { marketMcpApi } from "../../api/modules/marketMcp";
import { fetchBbkBySource, fetchTenantsBySource, BbkInfo, TenantSourceInfo } from "../../api/modules/userInfo";
import { useIframeStore } from "../../stores/iframeStore";
import { DEFAULT_SOURCE_ID } from "../../constants/identity";
import type { MarketSkill } from "../../api/modules/market";
import type { MarketMCPItem } from "../../api/types";

export type DistributeTargetType = "skill" | "mcp";

interface DistributeTargetModalProps {
  open: boolean;
  type: DistributeTargetType;
  item: MarketSkill | MarketMCPItem | null;
  sourceId: string;
  onClose: () => void;
  onSuccess: () => void;
}

export function DistributeTargetModal({
  open,
  type,
  item,
  sourceId,
  onClose,
  onSuccess,
}: DistributeTargetModalProps) {
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [targetMode, setTargetMode] = useState<"bbk_id" | "user_id">("bbk_id");
  const [bbkOptions, setBbkOptions] = useState<BbkInfo[]>([]);
  const [tenantOptions, setTenantOptions] = useState<TenantSourceInfo[]>([]);
  const [selectedBbkIds, setSelectedBbkIds] = useState<string[]>([]);
  const [selectedTenantIds, setSelectedTenantIds] = useState<string[]>([]);
  const [manualTenantIdsText, setManualTenantIdsText] = useState("");

  const resolvedSourceId = useIframeStore((state) => state.source) || DEFAULT_SOURCE_ID || sourceId;

  // 加载机构/用户列表
  useEffect(() => {
    if (!open) return;
    setLoading(true);
    setSelectedBbkIds([]);
    setSelectedTenantIds([]);
    setManualTenantIdsText("");
    Promise.all([
      fetchBbkBySource(resolvedSourceId),
      fetchTenantsBySource(resolvedSourceId),
    ])
      .then(([bbkList, tenantList]) => {
        setBbkOptions(bbkList);
        setTenantOptions(tenantList);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [open, resolvedSourceId]);

  // 按机构过滤用户
  const filteredTenantIds = useMemo(() => {
    if (targetMode === "bbk_id") {
      if (selectedBbkIds.length === 0) {
        return [];
      }
      return tenantOptions
        .filter((t) => selectedBbkIds.includes(t.bbk_id || ""))
        .map((t) => t.tenant_id);
    }
    return tenantOptions.map((t) => t.tenant_id);
  }, [targetMode, selectedBbkIds, tenantOptions]);

  // 手动输入的租户 ID
  const manualTenantIds = useMemo(() => {
    return Array.from(
      new Set(
        manualTenantIdsText
          .split(/[\s,]+/)
          .map((s) => s.trim())
          .filter(Boolean),
      ),
    );
  }, [manualTenantIdsText]);

  // 合并选择 + 手动输入（按机构时使用过滤后的用户列表）
  const finalTenantIds = useMemo(() => {
    if (targetMode === "bbk_id") {
      return filteredTenantIds;
    }
    return Array.from(new Set([...selectedTenantIds, ...manualTenantIds]));
  }, [targetMode, filteredTenantIds, selectedTenantIds, manualTenantIds]);

  // 切换模式时清空选择
  const handleModeChange = (mode: "bbk_id" | "user_id") => {
    setTargetMode(mode);
    setSelectedBbkIds([]);
    setSelectedTenantIds([]);
  };

  // 全选/清空
  const handleSelectAll = () => {
    setSelectedTenantIds(Array.from(new Set(filteredTenantIds)));
  };
  const handleClearAll = () => {
    setSelectedTenantIds([]);
  };

  // 提交分发
  const handleSubmit = async () => {
    if (!item || finalTenantIds.length === 0) return;
    setSubmitting(true);
    try {
      if (type === "skill") {
        const payload: DistributeRequest = {
          target_type: "user_id",
          target_values: finalTenantIds,
        };
        await marketApi.distributeSkill(sourceId, (item as MarketSkill).item_id, payload);
        message.success(`分发成功，共 ${finalTenantIds.length} 个用户`);
      } else {
        const result = await marketMcpApi.distributeMCP(
          (item as MarketMCPItem).item_id,
          {
            target_tenant_ids: finalTenantIds,
            overwrite: true,
          },
        );

        const items = Array.isArray(result.results) ? result.results : [];
        const succeeded = items.filter((r) => r.success);
        const failed = items.filter((r) => !r.success);

        if (failed.length > 0) {
          const successLines = succeeded.map((r) => {
            const suffix = r.bootstrapped ? " (已初始化)" : "";
            return `• ${r.tenant_id}${suffix}`;
          });
          const failureLines = failed.map(
            (r) => `• ${r.tenant_id}: ${r.error || "分发失败"}`,
          );
          Modal.confirm({
            title: succeeded.length > 0 ? "部分租户分发失败" : "分发失败",
            content: (
              <div style={{ display: "grid", gap: 8 }}>
                {succeeded.length > 0 ? (
                  <div style={{ display: "grid", gap: 4 }}>
                    <div>以下租户分发成功：</div>
                    <pre style={{ margin: 0, whiteSpace: "pre-wrap" }}>
                      {successLines.join("\n")}
                    </pre>
                  </div>
                ) : null}
                <div style={{ display: "grid", gap: 4 }}>
                  <div>以下租户分发失败：</div>
                  <pre style={{ margin: 0, whiteSpace: "pre-wrap" }}>
                    {failureLines.join("\n")}
                  </pre>
                </div>
              </div>
            ),
            okText: "关闭",
            cancelButtonProps: { style: { display: "none" } },
          });
        } else if (succeeded.length > 0) {
          message.success(`分发成功，共 ${succeeded.length} 个租户`);
        }
      }
      onSuccess();
      onClose();
    } catch (error) {
      console.error("分发失败:", error);
      message.error(error instanceof Error ? error.message : "分发失败");
    } finally {
      setSubmitting(false);
    }
  };

  const typeLabel = type === "skill" ? "技能" : "MCP";
  const hintText = type === "skill"
    ? "将当前技能分发到目标用户的工作空间中，用户可在「我的技能」中查看。"
    : "将当前市场 MCP 分发到目标租户的 default agent 中，如已存在同名 MCP 将覆盖。";

  return (
    <Modal
      open={open}
      title={`分发「${item?.name || ""}」`}
      onCancel={submitting ? undefined : onClose}
      onOk={handleSubmit}
      okText="分发"
      cancelText="取消"
      okButtonProps={{
        disabled: finalTenantIds.length === 0,
        loading: submitting,
      }}
      width={600}
    >
      <div style={{ display: "grid", gap: 12 }}>
        <div style={{ color: "#666", fontSize: 12 }}>
          {hintText}
        </div>
        <div style={{ fontWeight: 500 }}>
          当前条目：{item?.name || "-"}（共选择 {finalTenantIds.length} 个用户）
        </div>

        {/* 分发目标模式选择 */}
        <div style={{ display: "grid", gap: 8 }}>
          <div style={{ fontWeight: 500 }}>分发目标</div>
          <Radio.Group value={targetMode} onChange={(e) => handleModeChange(e.target.value)}>
            <Radio value="bbk_id">按机构</Radio>
            <Radio value="user_id">按用户</Radio>
          </Radio.Group>
        </div>

        {loading ? (
          <Spin size="small" style={{ marginLeft: 16 }} />
        ) : (
          <>
            {/* 按机构：多选机构 */}
            {targetMode === "bbk_id" && (
              <div style={{ display: "grid", gap: 8 }}>
                <div style={{ fontWeight: 500 }}>选择机构</div>
                <Select
                  mode="multiple"
                  placeholder="选择机构"
                  value={selectedBbkIds}
                  onChange={setSelectedBbkIds}
                  options={bbkOptions.map((b) => ({
                    label: b.bbk_name || b.bbk_id,
                    value: b.bbk_id,
                  }))}
                  style={{ width: "100%" }}
                />
                <div style={{ color: "#666", fontSize: 12 }}>
                  已选择 {selectedBbkIds.length} 个机构，涉及 {filteredTenantIds.length} 个用户
                </div>
              </div>
            )}

            {/* 按用户：网格卡片选择 */}
            {targetMode === "user_id" && (
              <div style={{ display: "grid", gap: 12 }}>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    gap: 8,
                  }}
                >
                  <div style={{ fontWeight: 500 }}>选择用户</div>
                  <div style={{ display: "flex", gap: 8 }}>
                    <Button size="small" onClick={handleSelectAll}>
                      全选
                    </Button>
                    <Button size="small" onClick={handleClearAll}>
                      清空
                    </Button>
                  </div>
                </div>

              {/* 用户网格卡片 */}
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
                  gap: 8,
                  maxHeight: 240,
                  overflowY: "auto",
                }}
              >
                {filteredTenantIds.map((tenantId) => {
                  const tenant = tenantOptions.find((t) => t.tenant_id === tenantId);
                  const displayName = tenant?.tenant_name
                    ? `${tenant.tenant_name} (${tenantId})`
                    : tenantId;
                  const selected = selectedTenantIds.includes(tenantId);
                  return (
                    <button
                      key={tenantId}
                      type="button"
                      onClick={() =>
                        setSelectedTenantIds(
                          selected
                            ? selectedTenantIds.filter((id) => id !== tenantId)
                            : [...selectedTenantIds, tenantId],
                        )
                      }
                      style={{
                        cursor: "pointer",
                        borderRadius: 8,
                        border: selected ? "1px solid #1677ff" : "1px solid #d9d9d9",
                        background: selected ? "#eff6ff" : "#fff",
                        padding: "12px 14px",
                        textAlign: "left",
                        position: "relative",
                        fontSize: 12,
                      }}
                    >
                      {selected ? (
                        <span style={{ position: "absolute", right: 10, top: 8 }}>
                          <CheckOutlined />
                        </span>
                      ) : null}
                      <span>{displayName}</span>
                    </button>
                  );
                })}
              </div>

              {/* 手动输入 */}
              <div>
                <div style={{ fontWeight: 500 }}>手动输入用户</div>
                <div style={{ marginTop: 8, marginBottom: 8, color: "#666", fontSize: 12 }}>
                  输入额外的用户ID，多个用户用空格或逗号分隔
                </div>
                <textarea
                  rows={3}
                  value={manualTenantIdsText}
                  onChange={(e) => setManualTenantIdsText(e.target.value)}
                  placeholder="例如：user001 user002 user003"
                  style={{
                    width: "100%",
                    padding: 8,
                    borderRadius: 6,
                    border: "1px solid #d9d9d9",
                    fontSize: 12,
                    resize: "none",
                  }}
                />
              </div>
              </div>
            )}
          </>
        )}
      </div>
    </Modal>
  );
}