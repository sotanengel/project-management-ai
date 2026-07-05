/** PMDFエンティティの型(全14種)。api-server(`GET /pmdf/{kind}`等)の
 * `entity_to_json_dict`出力形式(Noneフィールド省略)に対応する。
 *
 * 各インターフェースは表示に必要な主要フィールドを定義する(PmdfBase共通の
 * `pmdf_version`/`provenance`/`attachments`はentity-viewsでは汎用表示に
 * 委ねるため型上は省略可能な`Record<string, unknown>`経由で許容する)。
 */

export interface PmdfEntityBase {
  kind: string;
  id: string;
  pmdf_version?: string;
  provenance?: {
    created_by: string;
    approved_by?: string | null;
    updated_at: string;
  };
  attachments?: Array<{ path: string; sha256: string }>;
  [key: string]: unknown;
}

export interface Product extends PmdfEntityBase {
  kind: "product";
  name: string;
  vision?: string;
  target?: string | null;
  positioning?: string | null;
  lifecycle_stage?: string;
  north_star_metric?: string | null;
}

export interface Stakeholder extends PmdfEntityBase {
  kind: "stakeholder";
  name: string;
  role: string;
  organization?: string | null;
  interests?: string[];
  influence: string;
  contact_policy?: {
    personal_name?: string | null;
    channel?: string | null;
    frequency?: string | null;
  } | null;
}

export interface Persona extends PmdfEntityBase {
  kind: "persona";
  name: string;
  attributes?: Record<string, string>;
  pain_points?: string[];
  jobs: Array<{ situation: string; motivation: string; outcome: string }>;
}

export interface Objective extends PmdfEntityBase {
  kind: "objective";
  objective: string;
  key_results: Array<{
    description: string;
    target_value: number;
    current_value?: number | null;
  }>;
  period: string;
  parent_objective?: string | null;
}

export interface MetricTimeSeriesPoint {
  timestamp: string;
  value: number;
}

export interface Metric extends PmdfEntityBase {
  kind: "metric";
  name: string;
  definition?: string;
  calculation_method?: string;
  target_value: number | null;
  threshold_value: number | null;
  current_value: number | null;
  time_series?: MetricTimeSeriesPoint[];
}

export type RoadmapItemStatus =
  "planned" | "in_progress" | "done" | "cancelled";

export interface RoadmapItem extends PmdfEntityBase {
  kind: "roadmap_item";
  product?: string | null;
  theme: string;
  period: string;
  status: RoadmapItemStatus;
  dependencies?: string[];
  objective?: string;
}

export interface Story extends PmdfEntityBase {
  kind: "story";
  product?: string | null;
  title: string;
  as_a: string;
  i_want: string;
  so_that: string;
  acceptance_criteria: string[];
  priority: {
    method: string;
    reach?: number | null;
    impact?: number | null;
    confidence?: number | null;
    effort?: number | null;
    score?: number | null;
  };
  status: string;
  links?: { objective?: string | null; decisions?: string[] } | null;
}

export interface Experiment extends PmdfEntityBase {
  kind: "experiment";
  product?: string | null;
  hypothesis: string;
  design: string;
  success_criteria: string[];
  status: string;
  results?: string | null;
  learnings?: string | null;
}

export interface Decision extends PmdfEntityBase {
  kind: "decision";
  product?: string | null;
  background: string;
  options: Array<{
    name: string;
    description?: string | null;
    pros?: string[];
    cons?: string[];
  }>;
  chosen_option: string;
  rationale: string;
  rejected_reasons: Array<{ option: string; reason: string }>;
  approver?: string | null;
  autonomy_level: string;
}

export interface Release extends PmdfEntityBase {
  kind: "release";
  product?: string | null;
  name: string;
  scope: string[];
  go_no_go: string;
  released_at?: string | null;
  actuals?: Record<string, unknown>;
}

export interface Risk extends PmdfEntityBase {
  kind: "risk";
  product?: string | null;
  event: string;
  probability_score: number;
  impact_score: number;
  response_strategy: string;
  owner: string;
}

export interface Initiative extends PmdfEntityBase {
  kind: "initiative";
  product?: string | null;
  charter: string;
  approach: string;
  wbs?: Array<{ id: string; name: string; children?: unknown[] }>;
  schedule?: { start_date?: string | null; end_date?: string | null } | null;
  evm?: {
    planned_value?: number | null;
    earned_value?: number | null;
    actual_cost?: number | null;
    spi?: number | null;
    cpi?: number | null;
  } | null;
}

export interface Report extends PmdfEntityBase {
  kind: "report";
  product?: string | null;
  period: string;
  health_assessment: string;
  decisions_needed: string[];
  summary?: string | null;
}

export interface Approval extends PmdfEntityBase {
  kind: "approval";
  target: string;
  proposer: string;
  approver: string;
  decision: "approved" | "rejected";
  reason: string;
}

/** PMDF全14 kind文字列のユニオン。 */
export type PmdfKind =
  | "product"
  | "stakeholder"
  | "persona"
  | "objective"
  | "metric"
  | "roadmap_item"
  | "story"
  | "experiment"
  | "decision"
  | "release"
  | "risk"
  | "initiative"
  | "report"
  | "approval";

export const PMDF_KINDS: PmdfKind[] = [
  "product",
  "stakeholder",
  "persona",
  "objective",
  "metric",
  "roadmap_item",
  "story",
  "experiment",
  "decision",
  "release",
  "risk",
  "initiative",
  "report",
  "approval",
];

/** kind文字列からPMDF ID接頭辞へのマッピング(`packages/pmdf`の`KIND_TO_PREFIX`と一致させること)。 */
export const KIND_TO_PREFIX: Record<PmdfKind, string> = {
  product: "prod",
  stakeholder: "stakeholder",
  persona: "persona",
  objective: "obj",
  metric: "metric",
  roadmap_item: "roadmap",
  story: "story",
  experiment: "experiment",
  decision: "dec",
  release: "release",
  risk: "risk",
  initiative: "initiative",
  report: "report",
  approval: "approval",
};

/** PMDF ID(`<prefix>-<ULID>`)から対象のkindを推定する。未知の接頭辞は`null`。 */
export function inferKindFromId(id: string): PmdfKind | null {
  const separatorIndex = id.indexOf("-");
  if (separatorIndex < 0) {
    return null;
  }
  const prefix = id.slice(0, separatorIndex);
  const entry = (
    Object.entries(KIND_TO_PREFIX) as Array<[PmdfKind, string]>
  ).find(([, p]) => p === prefix);
  return entry ? entry[0] : null;
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
