import { useCallback, useEffect, useMemo, useState } from "react";
import { Database } from "lucide-react";
import { Modal, Select, Switch, Tooltip } from "antd";
import type { Dayjs } from "dayjs";
import dayjs from "dayjs";
import { htmlPreviewEventsApi } from "../../../../../api/modules/htmlPreviewEvents";
import type {
  HtmlPreviewClickSummaryItem,
  HtmlPreviewCustomerClickItem,
  HtmlPreviewListSummaryItem,
} from "../../../../../api/types/htmlPreviewEvents";
import { formatNumber } from "../../types";
import styles from "./index.module.less";

const { Option } = Select;

interface HtmlPreviewClickAnalysisProps {
  dateRange: [Dayjs, Dayjs];
  effectiveBbkIds?: string[];
  refreshKey?: number;
}

const safeNumber = (value: unknown): number =>
  typeof value === "number" && !Number.isNaN(value) ? value : 0;

const formatManagerName = (
  name?: string | null,
  userId?: string | null,
) => name || userId || "-";

const formatHtmlPreviewTime = (
  value?: string | null,
  format = "MM-DD HH:mm",
) => {
  if (!value) {
    return "-";
  }
  const normalized = value.includes("T") ? value : value.replace(" ", "T");
  const hasTimezone = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(normalized);
  return dayjs(hasTimezone ? normalized : `${normalized}Z`).format(format);
};

export default function HtmlPreviewClickAnalysis({
  dateRange,
  effectiveBbkIds,
  refreshKey,
}: HtmlPreviewClickAnalysisProps) {
  const [htmlPreviewClicks, setHtmlPreviewClicks] = useState<
    HtmlPreviewClickSummaryItem[]
  >([]);
  const [htmlPreviewLists, setHtmlPreviewLists] = useState<
    HtmlPreviewListSummaryItem[]
  >([]);
  const [htmlPreviewCustomerClicks, setHtmlPreviewCustomerClicks] = useState<
    HtmlPreviewCustomerClickItem[]
  >([]);
  const [selectedHtmlPreviewCustomer, setSelectedHtmlPreviewCustomer] =
    useState<HtmlPreviewCustomerClickItem | null>(null);
  const [selectedHtmlPreviewListKey, setSelectedHtmlPreviewListKey] =
    useState<string>("all");
  const [includeUnclickedCustomers, setIncludeUnclickedCustomers] =
    useState(false);
  const [htmlPreviewLoading, setHtmlPreviewLoading] = useState(false);

  const fetchHtmlPreviewClicks = useCallback(async () => {
    setHtmlPreviewLoading(true);
    try {
      const params = {
        startTime: dateRange[0].startOf("day").toISOString(),
        endTime: dateRange[1].endOf("day").toISOString(),
        bbkIds: effectiveBbkIds?.join(","),
        limit: 100,
      };
      const selectedListKey =
        selectedHtmlPreviewListKey === "all"
          ? null
          : selectedHtmlPreviewListKey;
      const detailParams = {
        ...params,
        listKey: selectedListKey,
      };
      const [summaryResult, listResult, customerResult] =
        await Promise.allSettled([
          htmlPreviewEventsApi.getSummary(detailParams),
          htmlPreviewEventsApi.getLists(params),
          htmlPreviewEventsApi.getCustomerClicks({
            ...detailParams,
            includeUnclicked: includeUnclickedCustomers,
            limit: 500,
          }),
        ]);
      if (summaryResult.status === "fulfilled") {
        setHtmlPreviewClicks(summaryResult.value.items || []);
      } else {
        console.error(
          "Failed to fetch HTML preview click summary:",
          summaryResult.reason,
        );
        setHtmlPreviewClicks([]);
      }
      if (listResult.status === "fulfilled") {
        setHtmlPreviewLists(listResult.value.items || []);
      } else {
        console.error(
          "Failed to fetch HTML preview list summary:",
          listResult.reason,
        );
        setHtmlPreviewLists([]);
      }
      if (customerResult.status === "fulfilled") {
        setHtmlPreviewCustomerClicks(customerResult.value.items || []);
      } else {
        console.error(
          "Failed to fetch HTML preview customer clicks:",
          customerResult.reason,
        );
        setHtmlPreviewCustomerClicks([]);
      }
    } catch (error) {
      console.error("Failed to fetch HTML preview click statistics:", error);
      setHtmlPreviewClicks([]);
      setHtmlPreviewLists([]);
      setHtmlPreviewCustomerClicks([]);
    } finally {
      setHtmlPreviewLoading(false);
    }
  }, [
    dateRange,
    effectiveBbkIds,
    includeUnclickedCustomers,
    selectedHtmlPreviewListKey,
  ]);

  useEffect(() => {
    fetchHtmlPreviewClicks();
  }, [fetchHtmlPreviewClicks, refreshKey]);

  useEffect(() => {
    if (
      selectedHtmlPreviewListKey !== "all" &&
      !htmlPreviewLists.some(
        (item) => item.list_key === selectedHtmlPreviewListKey,
      )
    ) {
      setSelectedHtmlPreviewListKey("all");
    }
  }, [htmlPreviewLists, selectedHtmlPreviewListKey]);

  const selectedHtmlPreviewList = useMemo(
    () =>
      htmlPreviewLists.find(
        (item) => item.list_key === selectedHtmlPreviewListKey,
      ) || null,
    [htmlPreviewLists, selectedHtmlPreviewListKey],
  );
  const displayedHtmlPreviewLists = useMemo(
    () =>
      selectedHtmlPreviewListKey === "all"
        ? htmlPreviewLists
        : htmlPreviewLists.filter(
            (item) => item.list_key === selectedHtmlPreviewListKey,
          ),
    [htmlPreviewLists, selectedHtmlPreviewListKey],
  );
  const htmlPreviewListCount = displayedHtmlPreviewLists.length;
  const htmlPreviewInsightClicks = useMemo(
    () =>
      displayedHtmlPreviewLists.reduce(
        (sum, item) => sum + safeNumber(item.insight_count),
        0,
      ),
    [displayedHtmlPreviewLists],
  );
  const htmlPreviewPhoneClicks = useMemo(
    () =>
      displayedHtmlPreviewLists.reduce(
        (sum, item) => sum + safeNumber(item.phone_count),
        0,
      ),
    [displayedHtmlPreviewLists],
  );
  const htmlPreviewPlanClicks = useMemo(
    () =>
      displayedHtmlPreviewLists.reduce(
        (sum, item) => sum + safeNumber(item.plan_count),
        0,
      ),
    [displayedHtmlPreviewLists],
  );
  const htmlPreviewTotalClicks = useMemo(
    () =>
      displayedHtmlPreviewLists.reduce(
        (sum, item) => sum + safeNumber(item.total_click_count),
        0,
      ),
    [displayedHtmlPreviewLists],
  );
  const htmlPreviewMaxActionClicks = Math.max(
    htmlPreviewInsightClicks,
    htmlPreviewPhoneClicks,
    htmlPreviewPlanClicks,
    1,
  );
  const htmlPreviewActionTotal =
    htmlPreviewInsightClicks + htmlPreviewPhoneClicks + htmlPreviewPlanClicks;
  const htmlPreviewInsightPercent =
    htmlPreviewActionTotal > 0
      ? Math.round((htmlPreviewInsightClicks / htmlPreviewActionTotal) * 100)
      : 0;
  const htmlPreviewPhonePercent =
    htmlPreviewActionTotal > 0
      ? Math.round((htmlPreviewPhoneClicks / htmlPreviewActionTotal) * 100)
      : 0;
  const htmlPreviewPlanPercent =
    htmlPreviewActionTotal > 0
      ? Math.round((htmlPreviewPlanClicks / htmlPreviewActionTotal) * 100)
      : 0;
  const htmlPreviewCustomerTotal = useMemo(
    () =>
      displayedHtmlPreviewLists.reduce(
        (sum, item) => sum + safeNumber(item.customer_count),
        0,
      ),
    [displayedHtmlPreviewLists],
  );
  const htmlPreviewClickedCustomerCount = useMemo(
    () =>
      displayedHtmlPreviewLists.reduce(
        (sum, item) => sum + safeNumber(item.clicked_customer_count),
        0,
      ),
    [displayedHtmlPreviewLists],
  );
  const htmlPreviewLatestClick = useMemo(() => {
    const sortedClickTimes = htmlPreviewClicks
      .map((item) => item.last_clicked_at)
      .filter(Boolean)
      .sort();
    const latest = sortedClickTimes[sortedClickTimes.length - 1];
    return formatHtmlPreviewTime(latest, "YYYY-MM-DD HH:mm");
  }, [htmlPreviewClicks]);
  const hasHtmlPreviewAnalysisData =
    htmlPreviewClicks.length > 0 ||
    htmlPreviewLists.length > 0 ||
    htmlPreviewCustomerClicks.length > 0;

  return (
    <>
      <section
        className={styles.htmlPreviewSection}
        data-testid="html-preview-click-section"
      >
        <article className={styles.panelLarge}>
          <div className={styles.panelHeader}>
            <h3 className={styles.panelTitle}>客户经营点击分析</h3>
            <span className={styles.panelMeta}>
              最近点击：{htmlPreviewLatestClick}
            </span>
          </div>
          <div className={styles.htmlPreviewFilters}>
            <Select
              className={styles.htmlPreviewListSelect}
              value={selectedHtmlPreviewListKey}
              onChange={setSelectedHtmlPreviewListKey}
              placeholder="全部名单"
              showSearch
              optionFilterProp="label"
            >
              <Option value="all" label="全部名单">
                全部名单
              </Option>
              {htmlPreviewLists.map((item) => (
                <Option
                  key={item.list_key}
                  value={item.list_key}
                  label={item.list_name}
                >
                  {item.list_name}
                </Option>
              ))}
            </Select>
            <label className={styles.htmlPreviewSwitch}>
              <Switch
                size="small"
                checked={includeUnclickedCustomers}
                onChange={setIncludeUnclickedCustomers}
              />
              <span>显示未点击客户</span>
            </label>
          </div>
          {!hasHtmlPreviewAnalysisData ? (
            <div className={styles.emptyChartState}>
              <Database className={styles.emptyBreakdownIcon} />
              <span>
                {htmlPreviewLoading ? "加载中..." : "暂无客户经营点击数据"}
              </span>
            </div>
          ) : (
            <div className={styles.htmlPreviewDashboard}>
              <div className={styles.htmlPreviewStats}>
                <div className={styles.htmlPreviewStatCard}>
                  <span>名单数</span>
                  <strong>{formatNumber(htmlPreviewListCount)}</strong>
                </div>
                <div className={styles.htmlPreviewStatCard}>
                  <span>名单总客户数</span>
                  <strong>{formatNumber(htmlPreviewCustomerTotal)}</strong>
                </div>
                <div className={styles.htmlPreviewStatCard}>
                  <span>被点击客户数</span>
                  <strong>
                    {formatNumber(htmlPreviewClickedCustomerCount)}
                  </strong>
                </div>
                <div className={styles.htmlPreviewStatCard}>
                  <span>点击总数</span>
                  <strong>{formatNumber(htmlPreviewTotalClicks)}</strong>
                </div>
              </div>
              <div className={styles.htmlPreviewDistribution}>
                <div className={styles.htmlPreviewTopTitle}>点击分布</div>
                <div className={styles.htmlPreviewDistributionRows}>
                  <div className={styles.htmlPreviewDistributionRow}>
                    <div className={styles.htmlPreviewDistributionMeta}>
                      <span>洞察</span>
                      <strong>
                        {formatNumber(htmlPreviewInsightClicks)}
                        <em>{htmlPreviewInsightPercent}%</em>
                      </strong>
                    </div>
                    <div className={styles.htmlPreviewDistributionTrack}>
                      <i
                        className={styles.htmlPreviewInsightBar}
                        style={{
                          width: `${Math.max(
                            6,
                            (htmlPreviewInsightClicks /
                              htmlPreviewMaxActionClicks) *
                              100,
                          )}%`,
                        }}
                      />
                    </div>
                  </div>
                  <div className={styles.htmlPreviewDistributionRow}>
                    <div className={styles.htmlPreviewDistributionMeta}>
                      <span>电访</span>
                      <strong>
                        {formatNumber(htmlPreviewPhoneClicks)}
                        <em>{htmlPreviewPhonePercent}%</em>
                      </strong>
                    </div>
                    <div className={styles.htmlPreviewDistributionTrack}>
                      <i
                        className={styles.htmlPreviewPhoneBar}
                        style={{
                          width: `${Math.max(
                            6,
                            (htmlPreviewPhoneClicks /
                              htmlPreviewMaxActionClicks) *
                              100,
                          )}%`,
                        }}
                      />
                    </div>
                  </div>
                  <div className={styles.htmlPreviewDistributionRow}>
                    <div className={styles.htmlPreviewDistributionMeta}>
                      <span>查看方案</span>
                      <strong>
                        {formatNumber(htmlPreviewPlanClicks)}
                        <em>{htmlPreviewPlanPercent}%</em>
                      </strong>
                    </div>
                    <div className={styles.htmlPreviewDistributionTrack}>
                      <i
                        className={styles.htmlPreviewPlanBar}
                        style={{
                          width: `${Math.max(
                            6,
                            (htmlPreviewPlanClicks /
                              htmlPreviewMaxActionClicks) *
                              100,
                          )}%`,
                        }}
                      />
                    </div>
                  </div>
                </div>
              </div>
              <div className={styles.htmlPreviewTopList}>
                <div className={styles.htmlPreviewTopTitle}>名单点击概览</div>
                {displayedHtmlPreviewLists.slice(0, 5).map((item) => (
                  <div
                    key={item.list_key}
                    className={styles.htmlPreviewListRow}
                  >
                    <Tooltip
                      title={item.file_name || item.file_url || item.list_name}
                      placement="top"
                    >
                      <span className={styles.htmlPreviewTopName}>
                        {item.list_name}
                      </span>
                    </Tooltip>
                    <div className={styles.htmlPreviewListMetrics}>
                      <span>
                        <em>名单客户</em>
                        <strong>{formatNumber(item.customer_count)}</strong>
                      </span>
                      <span>
                        <em>点击客户</em>
                        <strong>
                          {formatNumber(item.clicked_customer_count)}
                        </strong>
                      </span>
                      <span>
                        <em>洞察</em>
                        <strong>{formatNumber(item.insight_count)}</strong>
                      </span>
                      <span>
                        <em>电访</em>
                        <strong>{formatNumber(item.phone_count)}</strong>
                      </span>
                      <span>
                        <em>查看方案</em>
                        <strong>{formatNumber(item.plan_count)}</strong>
                      </span>
                    </div>
                  </div>
                ))}
                {displayedHtmlPreviewLists.length === 0 && (
                  <div className={styles.htmlPreviewEmptyLine}>
                    暂无名单点击概览数据
                  </div>
                )}
              </div>
              <div className={styles.htmlPreviewEventList}>
                <div className={styles.htmlPreviewTopTitle}>客户点击明细</div>
                {selectedHtmlPreviewList && (
                  <div className={styles.htmlPreviewSelectedList}>
                    当前名单：{selectedHtmlPreviewList.list_name}
                  </div>
                )}
                {htmlPreviewCustomerClicks.length === 0 ? (
                  <div className={styles.htmlPreviewEmptyLine}>
                    暂无客户点击明细
                  </div>
                ) : (
                  <div className={styles.htmlPreviewCustomerTable}>
                    <div className={styles.htmlPreviewCustomerHeader}>
                      <span>客户</span>
                      <span>洞察</span>
                      <span>电访</span>
                      <span>查看方案</span>
                      <span>总点击</span>
                      <span>客户经理</span>
                      <span>最近</span>
                    </div>
                    {htmlPreviewCustomerClicks.map((item) => (
                      <div
                        key={`${item.customer_id || item.customer_name}-${
                          item.last_clicked_at || ""
                        }`}
                        className={styles.htmlPreviewCustomerRow}
                      >
                        <div className={styles.htmlPreviewCustomerCell}>
                          <span className={styles.htmlPreviewCustomerName}>
                            {item.customer_name || "未知客户"}
                          </span>
                          {item.customer_id && (
                            <span className={styles.htmlPreviewCustomerId}>
                              {item.customer_id}
                            </span>
                          )}
                        </div>
                        <strong>{formatNumber(item.insight_count)}</strong>
                        <strong>{formatNumber(item.phone_count)}</strong>
                        <strong>{formatNumber(item.plan_count)}</strong>
                        <strong>{formatNumber(item.total_click_count)}</strong>
                        <div className={styles.htmlPreviewManagerCell}>
                          <span>
                            {formatManagerName(
                              item.last_clicked_user_name,
                              item.last_clicked_user_id,
                            )}
                          </span>
                          {item.manager_clicks?.length ? (
                            <button
                              type="button"
                              onClick={() =>
                                setSelectedHtmlPreviewCustomer(item)
                              }
                            >
                              详情
                            </button>
                          ) : null}
                        </div>
                        <span className={styles.htmlPreviewEventTime}>
                          {formatHtmlPreviewTime(item.last_clicked_at)}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}
        </article>
      </section>

      <Modal
        open={Boolean(selectedHtmlPreviewCustomer)}
        title={
          selectedHtmlPreviewCustomer
            ? `${selectedHtmlPreviewCustomer.customer_name} 客户经理点击详情`
            : "客户经理点击详情"
        }
        footer={null}
        width={640}
        onCancel={() => setSelectedHtmlPreviewCustomer(null)}
      >
        <div className={styles.htmlPreviewManagerDetail}>
          <div className={styles.htmlPreviewManagerDetailHeader}>
            <span>客户经理</span>
            <span>洞察</span>
            <span>电访</span>
            <span>查看方案</span>
            <span>总点击</span>
            <span>最近</span>
          </div>
          {selectedHtmlPreviewCustomer?.manager_clicks?.map((item) => (
            <div
              key={`${item.user_id}-${item.last_clicked_at || ""}`}
              className={styles.htmlPreviewManagerDetailRow}
            >
              <span>{formatManagerName(item.user_name, item.user_id)}</span>
              <strong>{formatNumber(item.insight_count)}</strong>
              <strong>{formatNumber(item.phone_count)}</strong>
              <strong>{formatNumber(item.plan_count)}</strong>
              <strong>{formatNumber(item.total_click_count)}</strong>
              <span>{formatHtmlPreviewTime(item.last_clicked_at)}</span>
            </div>
          ))}
        </div>
      </Modal>
    </>
  );
}
