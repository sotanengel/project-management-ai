/** PMDFエンティティの型(ダッシュボード表示に必要な最小フィールドのみ)。 */

export interface Product {
  kind: "product";
  id: string;
  name: string;
  lifecycle_stage?: string;
}

export interface MetricTimeSeriesPoint {
  timestamp: string;
  value: number;
}

export interface Metric {
  kind: "metric";
  id: string;
  name: string;
  target_value: number;
  threshold_value: number;
  current_value: number | null;
  time_series?: MetricTimeSeriesPoint[];
}

export type RoadmapItemStatus =
  "planned" | "in_progress" | "done" | "cancelled";

export interface RoadmapItem {
  kind: "roadmap_item";
  id: string;
  product: string;
  theme: string;
  period: string;
  status: RoadmapItemStatus;
}

/** 直近のエージェント活動(agent.activityイベント/チャットタスク由来)。 */
export interface AgentActivityItem {
  id: string;
  task_id: string;
  status: "pending" | "running" | "done" | "failed";
  intent?: string | null;
  product_id?: string | null;
  timestamp: string;
}
