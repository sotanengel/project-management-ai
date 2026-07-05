import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { listApprovals, listPmdfEntities } from "../api/client";
import type { Metric, Product, RoadmapItem } from "../api/pmdfTypes";
import { useAppState } from "../state/useAppState";
import { KpiChart } from "../components/KpiChart";
import { RoadmapProgress } from "../components/RoadmapProgress";
import { VirtualizedList } from "../components/VirtualizedList";
import styles from "./Dashboard.module.css";

const ACTIVITY_STATUS_LABELS: Record<string, string> = {
  pending: "受付済み",
  running: "実行中",
  done: "完了",
  failed: "失敗",
};

const ROADMAP_STATUS_LABELS: Record<string, string> = {
  planned: "計画中",
  in_progress: "進行中",
  done: "完了",
  cancelled: "中止",
};

export function Dashboard() {
  const { pendingApprovalCount, recentActivity } = useAppState();
  const [selectedProductId, setSelectedProductId] = useState<string | null>(
    null,
  );

  const productsQuery = useQuery({
    queryKey: ["pmdf", "product"],
    queryFn: () => listPmdfEntities<Product>("product"),
  });

  const metricsQuery = useQuery({
    queryKey: ["pmdf", "metric"],
    queryFn: () => listPmdfEntities<Metric>("metric"),
  });

  const roadmapQuery = useQuery({
    queryKey: ["pmdf", "roadmap_item"],
    queryFn: () => listPmdfEntities<RoadmapItem>("roadmap_item"),
  });

  // 未承認件数はWebSocketで更新される値(useAppState)を優先しつつ、
  // 初期表示時(WebSocketイベント未受信)はAPIから取得した件数で補う。
  const approvalsQuery = useQuery({
    queryKey: ["approvals", "pending"],
    queryFn: () => listApprovals("pending"),
  });

  const products = productsQuery.data ?? [];
  const effectiveProductId = selectedProductId ?? products[0]?.id ?? null;

  const roadmapItemsForProduct = useMemo(() => {
    const items = roadmapQuery.data ?? [];
    if (!effectiveProductId) {
      return items;
    }
    return items.filter((item) => item.product === effectiveProductId);
  }, [roadmapQuery.data, effectiveProductId]);

  const displayedApprovalCount =
    pendingApprovalCount > 0
      ? pendingApprovalCount
      : (approvalsQuery.data?.length ?? 0);

  return (
    <div className={styles.container}>
      <div className={styles.productSelectRow}>
        <label htmlFor="product-select">プロダクト</label>
        <select
          id="product-select"
          value={effectiveProductId ?? ""}
          onChange={(event) => setSelectedProductId(event.target.value)}
        >
          {products.map((product) => (
            <option key={product.id} value={product.id}>
              {product.name}
            </option>
          ))}
        </select>
      </div>

      <div className={styles.grid}>
        <section className={styles.panel}>
          <h2>KPI推移</h2>
          <div className={styles.kpiList}>
            {(metricsQuery.data ?? []).map((metric) => (
              <KpiChart key={metric.id} metric={metric} />
            ))}
          </div>
        </section>

        <section className={styles.panel}>
          <RoadmapProgress items={roadmapItemsForProduct} />
          {roadmapItemsForProduct.length > 0 && (
            <div className={styles.roadmapListWrapper}>
              <VirtualizedList
                items={roadmapItemsForProduct}
                estimateSize={36}
                height={200}
                getKey={(item) => item.id}
                renderItem={(item) => (
                  <div
                    className={styles.roadmapRow}
                    data-testid="roadmap-item-row"
                  >
                    <span>{item.theme}</span>
                    <span className={styles.roadmapPeriod}>{item.period}</span>
                    <span>
                      {ROADMAP_STATUS_LABELS[item.status] ?? item.status}
                    </span>
                  </div>
                )}
              />
            </div>
          )}
        </section>

        <section className={styles.panel}>
          <h2>未承認件数</h2>
          <p
            className={styles.approvalCount}
            data-testid="pending-approval-count"
          >
            {displayedApprovalCount}
          </p>
        </section>

        <section className={styles.panel}>
          <h2>直近のエージェント活動</h2>
          {recentActivity.length === 0 ? (
            <p className={styles.noData}>活動履歴がありません</p>
          ) : (
            <VirtualizedList
              items={recentActivity}
              estimateSize={44}
              height={280}
              getKey={(item) => item.task_id}
              renderItem={(item) => (
                <div className={styles.activityRow} data-testid="activity-row">
                  <span className={styles.activityTaskId}>{item.task_id}</span>
                  <span className={styles.activityStatus}>
                    {ACTIVITY_STATUS_LABELS[item.status] ?? item.status}
                  </span>
                  {item.intent && (
                    <span className={styles.activityIntent}>{item.intent}</span>
                  )}
                </div>
              )}
            />
          )}
        </section>
      </div>
    </div>
  );
}
