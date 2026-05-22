import { useEffect, useRef, useState } from "react";
import {
  Alert,
  Button,
  Card,
  InputNumber,
  Result,
  Space,
  Spin,
  Switch,
  Tag,
} from "antd";
import { useTranslation } from "react-i18next";

import { PageHeader } from "@/components/PageHeader";
import { useAppMessage } from "@/hooks/useAppMessage";
import { sourceSystemConfigApi } from "@/api/modules/sourceSystemConfig";
import type {
  CurrentSourceSystemConfigResponse,
  SourceSystemConfig,
} from "@/api/types/sourceSystemConfig";
import { useIframeStore } from "@/stores/iframeStore";
import { useSourceSystemConfigStore } from "@/stores/sourceSystemConfigStore";
import { DEFAULT_SOURCE_ID } from "@/constants/identity";

import {
  CURRENT_SOURCE_SYSTEM_CONFIG_SWITCHES,
  TOOL_RESULT_COMPACT_NUMBER_FIELDS,
  readRegisteredSwitchValue,
  readToolResultCompactConfig,
  validateToolResultCompactConfig,
  writeRegisteredSwitchValue,
  writeToolResultCompactValue,
} from "./registry";
import styles from "./index.module.less";

function formatUpdatedAt(value?: string | null): string {
  if (!value) {
    return "未保存";
  }
  return value;
}

export default function SystemConfigPage() {
  const { t } = useTranslation();
  const { message } = useAppMessage();
  const isSuperManager = useIframeStore((state) => state.isSuperManager);
  const manager = useIframeStore((state) => state.manager);
  const activeSourceId =
    useIframeStore((state) => state.source) || DEFAULT_SOURCE_ID;
  const loadEffectiveConfig = useSourceSystemConfigStore(
    (state) => state.loadEffectiveConfig,
  );
  const canManage = isSuperManager || manager;
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [record, setRecord] =
    useState<CurrentSourceSystemConfigResponse | null>(null);
  const [draftConfig, setDraftConfig] = useState<SourceSystemConfig>({});
  const requestSeqRef = useRef(0);
  const activeSourceRef = useRef(activeSourceId);

  useEffect(() => {
    activeSourceRef.current = activeSourceId;
  }, [activeSourceId]);

  const beginRequest = (sourceId: string) => {
    requestSeqRef.current += 1;
    return {
      sourceId,
      requestId: requestSeqRef.current,
    };
  };

  const isCurrentRequest = (request: {
    sourceId: string;
    requestId: number;
  }) => {
    return (
      activeSourceRef.current === request.sourceId &&
      requestSeqRef.current === request.requestId
    );
  };

  const isLoadedSourceCurrent =
    record !== null && record.source_id === activeSourceId;
  const formDisabled = loading || saving || !!error || !isLoadedSourceCurrent;

  useEffect(() => {
    if (!canManage) {
      requestSeqRef.current += 1;
      setLoading(false);
      setSaving(false);
      setError(null);
      setRecord(null);
      setDraftConfig({});
      return;
    }

    const request = beginRequest(activeSourceId);
    setLoading(true);
    setSaving(false);
    setError(null);
    setRecord(null);
    setDraftConfig({});

    sourceSystemConfigApi
      .getCurrent()
      .then((response) => {
        if (
          !isCurrentRequest(request) ||
          response.source_id !== request.sourceId
        ) {
          return;
        }
        setRecord(response);
        setDraftConfig(response.config);
      })
      .catch((requestError) => {
        if (!isCurrentRequest(request)) {
          return;
        }
        setError(
          requestError instanceof Error
            ? requestError.message
            : String(requestError),
        );
      })
      .finally(() => {
        if (isCurrentRequest(request)) {
          setLoading(false);
        }
      });
  }, [activeSourceId, canManage]);

  if (!canManage) {
    return (
      <div className={styles.systemConfigPage}>
        <PageHeader
          parent={t("nav.settings")}
          current={t("nav.currentSourceConfig", {
            defaultValue: "当前 Source 配置",
          })}
        />
        <div className={styles.centerState}>
          <Result
            status="403"
            title="403"
            subTitle={t("sourceSystemConfigPage.forbidden", {
              defaultValue: "仅管理员可访问当前 Source 系统配置页面。",
            })}
          />
        </div>
      </div>
    );
  }

  const handleSwitchChange = (key: string, checked: boolean) => {
    if (formDisabled) {
      return;
    }
    const definition = CURRENT_SOURCE_SYSTEM_CONFIG_SWITCHES.find(
      (item) => item.key === key,
    );
    if (!definition) {
      return;
    }
    setDraftConfig((previous) =>
      writeRegisteredSwitchValue(previous, definition, checked),
    );
  };

  const handleToolResultEnabledChange = (checked: boolean) => {
    if (formDisabled) {
      return;
    }
    setDraftConfig((previous) =>
      writeToolResultCompactValue(previous, "enabled", checked),
    );
  };

  const handleToolResultNumberChange = (
    key: (typeof TOOL_RESULT_COMPACT_NUMBER_FIELDS)[number]["key"],
    value: number | null,
  ) => {
    if (formDisabled || typeof value !== "number") {
      return;
    }
    setDraftConfig((previous) =>
      writeToolResultCompactValue(previous, key, value),
    );
  };

  const handleSave = async () => {
    if (formDisabled) {
      return;
    }
    const validationError = validateToolResultCompactConfig(
      readToolResultCompactConfig(draftConfig),
    );
    if (validationError) {
      setError(validationError);
      message.error(validationError);
      return;
    }
    const request = beginRequest(activeSourceId);
    setSaving(true);
    setError(null);
    try {
      const nextRecord = await sourceSystemConfigApi.updateCurrent({
        config: draftConfig,
      });
      if (
        !isCurrentRequest(request) ||
        nextRecord.source_id !== request.sourceId
      ) {
        return;
      }
      setRecord(nextRecord);
      setDraftConfig(nextRecord.config);
      await loadEffectiveConfig(request.sourceId);
      if (!isCurrentRequest(request)) {
        return;
      }
      message.success(
        t("sourceSystemConfigPage.saveSuccess", {
          defaultValue: "当前 Source 配置已保存",
        }),
      );
    } catch (requestError) {
      const nextError =
        requestError instanceof Error
          ? requestError.message
          : String(requestError);
      if (!isCurrentRequest(request)) {
        return;
      }
      setError(nextError);
      message.error(nextError);
    } finally {
      if (isCurrentRequest(request)) {
        setSaving(false);
      }
    }
  };

  const toolResultCompactConfig = readToolResultCompactConfig(draftConfig);

  const handleDelete = async () => {
    if (formDisabled) {
      return;
    }
    const request = beginRequest(activeSourceId);
    setSaving(true);
    setError(null);
    try {
      await sourceSystemConfigApi.deleteCurrent();
      if (!isCurrentRequest(request)) {
        return;
      }
      const nextRecord = await sourceSystemConfigApi.getCurrent();
      if (
        !isCurrentRequest(request) ||
        nextRecord.source_id !== request.sourceId
      ) {
        return;
      }
      setRecord(nextRecord);
      setDraftConfig(nextRecord.config);
      await loadEffectiveConfig(request.sourceId);
      if (!isCurrentRequest(request)) {
        return;
      }
      message.success(
        t("sourceSystemConfigPage.deleteSuccess", {
          defaultValue: "当前 Source 配置已恢复默认态",
        }),
      );
    } catch (requestError) {
      const nextError =
        requestError instanceof Error
          ? requestError.message
          : String(requestError);
      if (!isCurrentRequest(request)) {
        return;
      }
      setError(nextError);
      message.error(nextError);
    } finally {
      if (isCurrentRequest(request)) {
        setSaving(false);
      }
    }
  };

  return (
    <div className={styles.systemConfigPage}>
      <PageHeader
        parent={t("nav.settings")}
        current={t("nav.currentSourceConfig", {
          defaultValue: "系统特性配置",
        })}
        subRow={
          <Space size={8}>
            <Tag color="blue">{activeSourceId}</Tag>
            {record ? (
              <Tag color={record.is_default ? "default" : "gold"}>
                {record.is_default
                  ? t("sourceSystemConfigPage.defaultState", {
                      defaultValue: "继承默认值",
                    })
                  : t("sourceSystemConfigPage.overrideState", {
                      defaultValue: "存在显式覆盖",
                    })}
              </Tag>
            ) : null}
          </Space>
        }
      />
      <div className={styles.pageBody}>
        {error ? (
          <Alert
            type="error"
            showIcon
            message={t("sourceSystemConfigPage.loadFailed", {
              defaultValue: "当前 Source 配置加载失败",
            })}
            description={error}
          />
        ) : null}

        {loading ? (
          <div className={styles.centerState}>
            <Spin size="large" />
          </div>
        ) : (
          <>
            <Card className={styles.metaCard}>
              <div className={styles.metaGrid}>
                <div>
                  <span className={styles.metaLabel}>
                    {t("sourceSystemConfigPage.sourceLabel", {
                      defaultValue: "当前 Source",
                    })}
                  </span>
                  <span className={styles.metaValue}>{activeSourceId}</span>
                </div>
                <div>
                  <span className={styles.metaLabel}>
                    {t("sourceSystemConfigPage.versionLabel", {
                      defaultValue: "原始配置版本",
                    })}
                  </span>
                  <span className={styles.metaValue}>
                    {record?.version ?? 0}
                  </span>
                </div>
                <div>
                  <span className={styles.metaLabel}>
                    {t("sourceSystemConfigPage.updatedByLabel", {
                      defaultValue: "最近修改人",
                    })}
                  </span>
                  <span className={styles.metaValue}>
                    {record?.updated_by || "未保存"}
                  </span>
                </div>
                <div>
                  <span className={styles.metaLabel}>
                    {t("sourceSystemConfigPage.updatedAtLabel", {
                      defaultValue: "最近修改时间",
                    })}
                  </span>
                  <span className={styles.metaValue}>
                    {formatUpdatedAt(record?.updated_at)}
                  </span>
                </div>
              </div>
            </Card>

            <Card
              className={styles.switchCard}
              title={t("sourceSystemConfigPage.switchesTitle", {
                defaultValue: "受控功能开关",
              })}
            >
              <div className={styles.switchList}>
                {CURRENT_SOURCE_SYSTEM_CONFIG_SWITCHES.map((definition) => (
                  <div key={definition.key} className={styles.switchRow}>
                    <div className={styles.switchCopy}>
                      <span className={styles.switchTitle}>
                        {definition.title}
                      </span>
                      <span className={styles.switchDescription}>
                        {definition.description}
                      </span>
                    </div>
                    <Switch
                      checked={readRegisteredSwitchValue(
                        draftConfig,
                        definition,
                      )}
                      disabled={formDisabled}
                      onChange={(checked) =>
                        handleSwitchChange(definition.key, checked)
                      }
                    />
                  </div>
                ))}
              </div>
            </Card>

            <Card
              className={styles.switchCard}
              title={t("sourceSystemConfigPage.toolResultCompactTitle", {
                defaultValue: "工具结果压缩配置",
              })}
            >
              <div className={styles.toolResultIntro}>
                {t("sourceSystemConfigPage.toolResultCompactIntro", {
                  defaultValue:
                    "未保存 source 覆盖时继承 Agent 配置；保存后当前 source 下请求使用这些阈值。",
                })}
              </div>
              <div className={styles.switchRow}>
                <div className={styles.switchCopy}>
                  <span className={styles.switchTitle}>
                    {t("sourceSystemConfigPage.toolResultEnabled", {
                      defaultValue: "启用工具结果压缩",
                    })}
                  </span>
                  <span className={styles.switchDescription}>
                    {t("sourceSystemConfigPage.toolResultEnabledDescription", {
                      defaultValue:
                        "关闭后当前 source 的历史工具结果不再压缩为 toolresult 文件。",
                    })}
                  </span>
                </div>
                <Switch
                  checked={toolResultCompactConfig.enabled}
                  disabled={formDisabled}
                  onChange={handleToolResultEnabledChange}
                />
              </div>
              <div className={styles.numberGrid}>
                {TOOL_RESULT_COMPACT_NUMBER_FIELDS.map((definition) => (
                  <label key={definition.key} className={styles.numberField}>
                    <span className={styles.numberLabel}>
                      {definition.title}
                    </span>
                    <InputNumber
                      min={definition.min}
                      max={definition.max}
                      step={definition.step}
                      value={toolResultCompactConfig[definition.key]}
                      disabled={formDisabled}
                      onChange={(value) =>
                        handleToolResultNumberChange(definition.key, value)
                      }
                    />
                  </label>
                ))}
              </div>
            </Card>

            <div className={styles.actionRow}>
              <Button
                danger
                onClick={handleDelete}
                disabled={formDisabled || record?.is_default}
              >
                {t("common.delete")}
              </Button>
              <Button
                type="primary"
                loading={saving}
                disabled={formDisabled}
                onClick={handleSave}
              >
                {t("common.save")}
              </Button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
