/** E10-1 サンプルシードと整合するエンティティID・初期データ。 */
export const PRODUCT_ID = "prod-01JZX0AAAA01BBBBCCCCDDDDEE";
export const ROADMAP_ID = "roadmap-01JZX1RRRR01BBBBCCCCDDDDEF";
export const STORY_ID = "story-01JZX4T8G2K9V6R5N4M3P2Q1R0";
export const EXPERIMENT_ID = "experiment-01JZX2EEEE01BBBBCCCCDDDDAB";
export const DECISION_ID = "dec-01JZX3DDDD01BBBBCCCCDDDDEF";
export const RELEASE_ID = "release-01JZX4RSEA01BBBBCCCCDDDDAB";
export const STAKEHOLDER_ID = "stakeholder-01JZX0SSSS01BBBBCCCCDDDDEF";
export const REPORT_ID = "report-01JZX5WWWW01BBBBCCCCDDDDAB";

export const INITIAL_PRODUCT = {
  kind: "product",
  id: PRODUCT_ID,
  name: "サンプルEC",
  vision: "誰もが安心して使える購買体験を提供する",
  target: "20-40代のオンライン購買者",
  positioning: "信頼と速さを両立するECプラットフォーム",
  lifecycle_stage: "growth",
  north_star_metric: "metric-01JZX0MMMM01BBBBCCCCDDDDEE",
  pmdf_version: "1.0.0",
  provenance: {
    created_by: "user:pdm-taro",
    approved_by: null,
    updated_at: "2026-07-01T09:00:00+09:00",
  },
  attachments: [],
};

export const INITIAL_ROADMAP = {
  kind: "roadmap_item",
  id: ROADMAP_ID,
  product: PRODUCT_ID,
  theme: "注文履歴の非会員向け提供",
  period: "2026-Q3",
  status: "planned",
  dependencies: [],
  objective: "obj-01JZX0KKKK01BBBBCCCCDDDDEF",
  pmdf_version: "1.0.0",
  provenance: {
    created_by: "user:pdm-taro",
    updated_at: "2026-07-01T09:00:00+09:00",
  },
  attachments: [],
};

export const INITIAL_STORY = {
  kind: "story",
  id: STORY_ID,
  product: PRODUCT_ID,
  title: "ゲスト購入でも注文履歴をメールから参照できる",
  as_a: "会員登録をしていない購入者",
  i_want: "注文完了メールのリンクから注文履歴を確認したい",
  so_that: "再度会員登録することなく購入内容を追跡できる",
  acceptance_criteria: [
    "注文完了メールに履歴参照用の一意なリンクが含まれる",
    "リンクは発行から30日間有効である",
  ],
  priority: {
    method: "RICE",
    reach: 4200,
    impact: 2,
    confidence: 0.8,
    effort: 3,
    score: 2240,
  },
  status: "ready",
  pmdf_version: "1.0.0",
  provenance: {
    created_by: "user:pdm-taro",
    approved_by: null,
    updated_at: "2026-07-01T09:00:00+09:00",
  },
  attachments: [],
};

export const INITIAL_EXPERIMENT = {
  kind: "experiment",
  id: EXPERIMENT_ID,
  product: PRODUCT_ID,
  hypothesis: "履歴リンクを提供すると再訪率が上がる",
  design: "A/Bテスト、対象は非会員購入者の50%",
  success_criteria: ["再訪率が5ポイント以上向上する"],
  status: "planned",
  results: null,
  learnings: null,
  pmdf_version: "1.0.0",
  provenance: {
    created_by: "user:pdm-taro",
    updated_at: "2026-07-01T09:00:00+09:00",
  },
  attachments: [],
};

export const INITIAL_DECISION = {
  kind: "decision",
  id: DECISION_ID,
  product: PRODUCT_ID,
  background: "非会員購入者から注文履歴確認の問い合わせが増えている",
  options: [
    {
      name: "メールリンク方式",
      description: "注文完了メールに履歴参照用リンクを埋め込む",
      pros: ["実装が軽量"],
      cons: ["リンク漏えいリスク"],
    },
  ],
  chosen_option: "メールリンク方式",
  rationale: "リードタイムとコストを踏まえ、軽量な方式を優先した",
  rejected_reasons: [],
  approver: STAKEHOLDER_ID,
  autonomy_level: "L1",
  pmdf_version: "1.0.0",
  provenance: {
    created_by: "agent:decision-record@v1",
    approved_by: null,
    updated_at: "2026-07-06T09:00:00+09:00",
  },
  attachments: [
    {
      path: "guest-order-spec.pdf",
      sha256:
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    },
  ],
};

export const INITIAL_STAKEHOLDER = {
  kind: "stakeholder",
  id: STAKEHOLDER_ID,
  name: "山田太郎",
  role: "営業部長",
  organization: "パートナー株式会社",
  interests: ["リードタイム短縮"],
  influence: "high",
  contact_policy: {
    personal_name: "山田太郎",
    channel: "email",
    frequency: "monthly",
  },
  pmdf_version: "1.0.0",
  provenance: {
    created_by: "agent:pm-copilot@v0.1.0",
    updated_at: "2026-07-01T09:00:00+09:00",
  },
  attachments: [],
};

export const INITIAL_RELEASE = {
  kind: "release",
  id: RELEASE_ID,
  product: PRODUCT_ID,
  name: "2026-Q3 第1弾リリース",
  scope: [STORY_ID],
  go_no_go: "pending",
  released_at: null,
  actuals: { incidents: 0, delay_days: 0 },
  pmdf_version: "1.0.0",
  provenance: {
    created_by: "user:pdm-taro",
    updated_at: "2026-07-01T09:00:00+09:00",
  },
  attachments: [],
};
