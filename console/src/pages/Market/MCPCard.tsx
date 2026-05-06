/**
 * 市场 MCP 卡片。
 *
 * 说明：
 * - 列表卡片布局尽量贴近 CmbCoworkAgent-main 的应用市场卡片
 * - 只保留 MCP 市场自己的动作：详情 / 分发 / 删除
 */
import { Button } from "antd";
import {
  DeleteOutlined,
  EditOutlined,
  EyeOutlined,
  RocketOutlined,
} from "@ant-design/icons";
import { Calendar, GitBranch } from "lucide-react";
import type { MarketMCPItem } from "../../api/types";

interface MCPCardProps {
  mcp: MarketMCPItem;
  onOpenDetail: () => void;
  onDistribute: () => void;
  onEdit?: () => void;
  onDelete: () => void;
  canEdit?: boolean;
}

const footerButtonStyle = {
  height: 28,
  paddingInline: 12,
  borderRadius: 10,
  fontSize: 12,
};

function formatDate(value?: string | null): string {
  if (!value) return "-";
  const normalized = value.includes("T") ? value : value.replace(" ", "T");
  const date = new Date(normalized);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString("zh-CN");
}

export function MCPCard({
  mcp,
  onOpenDetail,
  onDistribute,
  onEdit,
  onDelete,
  canEdit = false,
}: MCPCardProps) {
  return (
    <div
      onClick={onOpenDetail}
      style={{
        padding: 20,
        borderRadius: 20,
        border: "1px solid #f0eee6",
        background: "#faf9f5",
        cursor: "pointer",
        transition: "all 0.2s ease",
        boxShadow: "rgba(0, 0, 0, 0) 0px 0px 0px",
      }}
      onMouseEnter={(event) => {
        event.currentTarget.style.background = "#ffffff";
        event.currentTarget.style.borderColor = "#e8e6dc";
        event.currentTarget.style.boxShadow =
          "rgba(0, 0, 0, 0.06) 0px 4px 20px";
      }}
      onMouseLeave={(event) => {
        event.currentTarget.style.background = "#faf9f5";
        event.currentTarget.style.borderColor = "#f0eee6";
        event.currentTarget.style.boxShadow =
          "rgba(0, 0, 0, 0) 0px 0px 0px";
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "space-between",
          marginBottom: 12,
          gap: 12,
        }}
      >
        <div style={{ flex: 1, minWidth: 0 }}>
          <div
            style={{
              fontWeight: 500,
              fontSize: 15,
              lineHeight: "22px",
              color: "#141413",
            }}
          >
            {mcp.chinese_name ? (
              <>
                {mcp.chinese_name}
                <span style={{ marginLeft: 6, color: "#87867f", fontWeight: 400, fontSize: 14 }}>
                  ({mcp.name})
                </span>
              </>
            ) : (
              mcp.name
            )}
          </div>
          {mcp.description ? (
            <p
              style={{
                margin: "8px 0 0",
                fontSize: 14,
                lineHeight: "22px",
                color: "#87867f",
                display: "-webkit-box",
                WebkitLineClamp: 2,
                WebkitBoxOrient: "vertical",
                overflow: "hidden",
              }}
            >
              {mcp.description}
            </p>
          ) : null}
        </div>
      </div>

      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          flexWrap: "wrap",
          gap: 8,
          paddingTop: 12,
          borderTop: "1px solid #f0eee6",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 12,
            fontSize: 12,
            color: "#87867f",
          }}
        >
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 4,
              whiteSpace: "nowrap",
            }}
          >
            <Calendar size={12} />
            <span>{formatDate(mcp.created_at)}</span>
          </div>
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 4,
              whiteSpace: "nowrap",
            }}
          >
            <GitBranch size={12} />
            <span>v{mcp.version || "1.0.0"}</span>
          </div>
        </div>

        <div
          style={{ display: "flex", alignItems: "center", gap: 6 }}
          onClick={(event) => event.stopPropagation()}
        >
          <Button
            icon={<EyeOutlined />}
            onClick={onOpenDetail}
            style={{
              ...footerButtonStyle,
              color: "#5e5d59",
              borderColor: "#e8e6dc",
              background: "#f5f4ed",
              boxShadow:
                "#e8e6dc 0px 0px 0px 0px, #d1cfc5 0px 0px 0px 1px",
            }}
          >
            详情
          </Button>
          <Button
            type="primary"
            icon={<RocketOutlined />}
            onClick={onDistribute}
            style={{
              ...footerButtonStyle,
              background: "#c4956a",
              borderColor: "#c4956a",
              color: "#faf9f5",
              boxShadow:
                "#c4956a 0px 0px 0px 0px, #c4956a 0px 0px 0px 1px",
            }}
          >
            分发
          </Button>
          {canEdit ? (
            <Button
              icon={<EditOutlined />}
              onClick={onEdit}
              style={{
                ...footerButtonStyle,
                color: "#5e5d59",
                borderColor: "#e8e6dc",
                background: "#f5f4ed",
                boxShadow:
                  "#e8e6dc 0px 0px 0px 0px, #d1cfc5 0px 0px 0px 1px",
              }}
            >
              编辑
            </Button>
          ) : null}
          <Button
            danger
            icon={<DeleteOutlined />}
            onClick={onDelete}
            style={{
              ...footerButtonStyle,
              borderColor: "#fad4d4",
              color: "#b53333",
              background: "#ffffff",
            }}
          >
            删除
          </Button>
        </div>
      </div>
    </div>
  );
}
