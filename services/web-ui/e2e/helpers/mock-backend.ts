import type { Route } from "@playwright/test";
import {
  buildBundlePayload,
  decodeBundle,
  encodeBundle,
  entitiesMatch,
  extractBundleBytesFromMultipart,
} from "./bundle-mock";
import {
  DECISION_ID,
  EXPERIMENT_ID,
  INITIAL_DECISION,
  INITIAL_EXPERIMENT,
  INITIAL_PRODUCT,
  INITIAL_RELEASE,
  INITIAL_ROADMAP,
  INITIAL_STAKEHOLDER,
  INITIAL_STORY,
  PRODUCT_ID,
  RELEASE_ID,
  REPORT_ID,
  ROADMAP_ID,
  STAKEHOLDER_ID,
  STORY_ID,
} from "./seed-entities";

export interface Proposal {
  id: string;
  target: string;
  proposer: string;
  status: "proposed" | "approved" | "rejected";
  approver: string | null;
  reason: string | null;
  approval_entity_id: string | null;
  draft: Record<string, unknown> | null;
}

type EntityMap = Record<string, Record<string, unknown>>;

/** Playwright route 用のインメモリ PDM モックバックエンド。 */
export class MockPdmBackend {
  entities: Record<string, EntityMap> = {
    product: { [PRODUCT_ID]: structuredClone(INITIAL_PRODUCT) },
    roadmap_item: { [ROADMAP_ID]: structuredClone(INITIAL_ROADMAP) },
    story: { [STORY_ID]: structuredClone(INITIAL_STORY) },
    experiment: { [EXPERIMENT_ID]: structuredClone(INITIAL_EXPERIMENT) },
    decision: { [DECISION_ID]: structuredClone(INITIAL_DECISION) },
    release: { [RELEASE_ID]: structuredClone(INITIAL_RELEASE) },
    metric: {
      "metric-01JZX0MMMM01BBBBCCCCDDDDEE": {
        kind: "metric",
        id: "metric-01JZX0MMMM01BBBBCCCCDDDDEE",
        name: "月間再訪率",
        current_value: 0.42,
      },
    },
    stakeholder: {
      [STAKEHOLDER_ID]: structuredClone(INITIAL_STAKEHOLDER),
    },
    report: {
      [REPORT_ID]: {
        kind: "report",
        id: REPORT_ID,
        title: "週次レビュー 2026-W27",
        status: "draft",
      },
    },
  };

  /** 直近エクスポートしたバンドル(validate フォールバック用)。 */
  lastExportedBundle: Buffer | null = null;

  /** バンドル import 先(空ストア相当)。 */
  secondaryEntities: Record<string, EntityMap> = {};

  proposals: Proposal[] = [];
  /** L1実行許可: `${kind}:${id}` */
  approvedTargets = new Set<string>();
  taskSeq = 0;

  resetSecondaryStore(): void {
    this.secondaryEntities = {};
  }

  bundleMatchesPrimary(): boolean {
    for (const kindMap of Object.values(this.entities)) {
      for (const entity of Object.values(kindMap)) {
        const kind = String(entity.kind);
        const id = String(entity.id);
        const imported = this.secondaryEntities[kind]?.[id];
        if (!imported || !entitiesMatch(entity, imported)) {
          return false;
        }
      }
    }
    const bundle = buildBundlePayload(this.entities);
    for (const [path, hash] of Object.entries(bundle.attachments)) {
      const importedBundle = buildBundlePayload(this.secondaryEntities);
      if (importedBundle.attachments[path] !== hash) {
        return false;
      }
    }
    return true;
  }

  private nextProposalId(): string {
    return `proposal-e2e-${String(this.proposals.length + 1).padStart(2, "0")}`;
  }

  private nextTaskId(): string {
    this.taskSeq += 1;
    return `task-e2e-${String(this.taskSeq).padStart(3, "0")}`;
  }

  private listEntities(kind: string): Record<string, unknown>[] {
    return Object.values(this.entities[kind] ?? {});
  }

  private getEntity(kind: string, id: string): Record<string, unknown> | null {
    return this.entities[kind]?.[id] ?? null;
  }

  private putEntity(
    kind: string,
    id: string,
    payload: Record<string, unknown>,
  ): Record<string, unknown> {
    if (!this.entities[kind]) {
      this.entities[kind] = {};
    }
    this.entities[kind][id] = payload;
    return payload;
  }

  private pendingProposals(): Proposal[] {
    return this.proposals.filter((p) => p.status === "proposed");
  }

  private addProposal(
    target: string,
    draft: Record<string, unknown>,
    proposer = STAKEHOLDER_ID,
  ): Proposal {
    const proposal: Proposal = {
      id: this.nextProposalId(),
      target,
      proposer,
      status: "proposed",
      approver: null,
      reason: null,
      approval_entity_id: null,
      draft,
    };
    this.proposals.push(proposal);
    return proposal;
  }

  private applyApprovedProposal(proposal: Proposal): void {
    if (!proposal.draft) {
      return;
    }
    const kind = String(proposal.draft.kind ?? "");
    const id = String(proposal.draft.id ?? proposal.target);
    const existing = this.getEntity(kind, id);
    if (existing) {
      this.putEntity(kind, id, { ...existing, ...proposal.draft });
    }
    this.approvedTargets.add(`${kind}:${id}`);
  }

  private hasApproval(kind: string, id: string): boolean {
    return this.approvedTargets.has(`${kind}:${id}`);
  }

  handle(
    method: string,
    pathname: string,
    search: URLSearchParams,
    body: unknown,
    multipartData: Buffer | null = null,
    contentType?: string,
  ) {
    const json = (status: number, payload: unknown) => ({
      status,
      contentType: "application/json",
      body: JSON.stringify(payload),
    });
    const binary = (status: number, data: Buffer, headers: Record<string, string> = {}) => ({
      status,
      contentType: "application/gzip",
      body: data,
      headers,
    });

    if (method === "GET" && pathname === "/approvals") {
      const status = search.get("status");
      const list =
        status === "pending"
          ? this.pendingProposals()
          : this.proposals.filter((p) => p.status !== "proposed");
      return json(200, list);
    }

    const decideMatch = pathname.match(/^\/approvals\/([^/]+)\/decide$/);
    if (method === "POST" && decideMatch) {
      const proposalId = decideMatch[1];
      const proposal = this.proposals.find((p) => p.id === proposalId);
      if (!proposal) {
        return json(404, { detail: "起案が見つかりません" });
      }
      const req = body as { decision?: string; reason?: string };
      if (req.decision === "approved") {
        proposal.status = "approved";
        proposal.reason = req.reason ?? "承認";
        this.applyApprovedProposal(proposal);
      } else if (req.decision === "rejected") {
        proposal.status = "rejected";
        proposal.reason = req.reason ?? "差し戻し";
      }
      return json(200, proposal);
    }

    if (method === "POST" && pathname === "/approvals") {
      const req = body as { target?: string; proposer?: string };
      const target = req.target ?? PRODUCT_ID;
      const kind = target.startsWith("roadmap")
        ? "roadmap_item"
        : target.startsWith("release")
          ? "release"
          : target.startsWith("prod")
            ? "product"
            : "product";
      const entity = this.getEntity(kind, target);
      const proposal = this.addProposal(
        target,
        (entity as Record<string, unknown>) ?? { kind, id: target },
        req.proposer ?? STAKEHOLDER_ID,
      );
      return json(201, proposal);
    }

    const pmdfListMatch = pathname.match(/^\/pmdf\/([^/]+)$/);
    if (method === "GET" && pmdfListMatch) {
      return json(200, this.listEntities(pmdfListMatch[1]));
    }

    const pmdfGetMatch = pathname.match(/^\/pmdf\/([^/]+)\/([^/]+)$/);
    if (method === "GET" && pmdfGetMatch) {
      const [, kind, id] = pmdfGetMatch;
      const entity = this.getEntity(kind, id);
      if (!entity) {
        return json(404, { detail: `${kind}:${id} が見つかりません` });
      }
      return json(200, entity);
    }

    if (method === "PUT" && pmdfGetMatch) {
      const [, kind, id] = pmdfGetMatch;
      const updated = this.putEntity(kind, id, body as Record<string, unknown>);
      return json(200, updated);
    }

    if (method === "POST" && pathname === "/chat/instructions") {
      const req = body as { message?: string; product_id?: string };
      const message = req.message ?? "";
      const taskId = this.nextTaskId();
      if (message.includes("ビジョン")) {
        this.addProposal(PRODUCT_ID, {
          ...structuredClone(INITIAL_PRODUCT),
          id: PRODUCT_ID,
          kind: "product",
          vision: "ゲストにも安心な購買体験を届ける",
        });
      } else if (message.includes("ロードマップ")) {
        this.addProposal(ROADMAP_ID, {
          ...structuredClone(INITIAL_ROADMAP),
          id: ROADMAP_ID,
          kind: "roadmap_item",
          status: "committed",
        });
      } else if (message.includes("リリース")) {
        this.addProposal(RELEASE_ID, {
          ...structuredClone(INITIAL_RELEASE),
          id: RELEASE_ID,
          kind: "release",
          go_no_go: "go",
        });
      } else if (message.includes("週次レビュー")) {
        this.addProposal(REPORT_ID, {
          kind: "report",
          id: REPORT_ID,
          title: "週次レビュー 2026-W28",
          status: "pending_approval",
        });
      }
      return json(200, {
        id: taskId,
        status: "done",
        product_id: req.product_id ?? PRODUCT_ID,
        intent: "e2e-mock",
      });
    }

    if (method === "GET" && pathname === "/chat/tasks") {
      return json(200, []);
    }

    const roadmapConfirm = pathname.match(/^\/roadmap\/([^/]+)\/confirm$/);
    if (method === "POST" && roadmapConfirm) {
      const id = roadmapConfirm[1];
      if (!this.hasApproval("roadmap_item", id)) {
        return json(403, {
          detail: "承認レコードが必要です(L1業務)",
        });
      }
      const entity = this.getEntity("roadmap_item", id);
      if (!entity) {
        return json(404, { detail: `roadmap_item:${id} が見つかりません` });
      }
      return json(200, { confirmed: true, target: id });
    }

    const releaseGo = pathname.match(/^\/release\/([^/]+)\/go-no-go$/);
    if (method === "POST" && releaseGo) {
      const id = releaseGo[1];
      if (!this.hasApproval("release", id)) {
        return json(403, {
          detail: "承認レコードが必要です(L1業務)",
        });
      }
      return json(200, { go: true, target: id });
    }

    const decisionExec = pathname.match(/^\/pmdf\/decision\/([^/]+)\/execute$/);
    if (method === "POST" && decisionExec) {
      const id = decisionExec[1];
      if (!this.hasApproval("decision", id)) {
        return json(403, {
          detail: "承認レコードが必要です(L1業務)",
        });
      }
      return json(200, { executed: true, target: id });
    }

    const stakeholderSend = pathname.match(/^\/stakeholder\/([^/]+)\/send-message$/);
    if (method === "POST" && stakeholderSend) {
      const id = stakeholderSend[1];
      if (!this.hasApproval("stakeholder", id)) {
        return json(403, {
          detail: "承認レコードが必要です(L1業務)",
        });
      }
      return json(200, { sent: true, target: id });
    }

    if (method === "GET" && pathname === "/autonomy/emergency-stop/status") {
      return json(200, { emergency_stopped: false });
    }

    if (method === "GET" && pathname === "/autonomy") {
      return json(200, [
        { product_id: PRODUCT_ID, business_function: "vision", level: "L1" },
        { product_id: PRODUCT_ID, business_function: "roadmap", level: "L1" },
        { product_id: PRODUCT_ID, business_function: "backlog", level: "L2" },
        { product_id: PRODUCT_ID, business_function: "experiment", level: "L2" },
        { product_id: PRODUCT_ID, business_function: "release", level: "L1" },
        {
          product_id: PRODUCT_ID,
          business_function: "decision_record",
          level: "L3",
        },
        {
          product_id: PRODUCT_ID,
          business_function: "periodic_review",
          level: "L1",
        },
      ]);
    }

    if (method === "GET" && pathname === "/costs/summary") {
      return json(200, {
        period: "2026-07",
        budget_monthly_jpy: 50000,
        total_spend_jpy: 10000,
        consumption_ratio: 0.2,
        budget_status: "ok",
        by_model: [],
        by_logical_name: [],
        by_day: [],
      });
    }

    if (method === "GET" && pathname === "/audit/records") {
      return json(200, []);
    }

    if (method === "POST" && pathname === "/bundles/export") {
      const req = body as { sanitize_profile?: string | null };
      const payload = buildBundlePayload(this.entities, {
        sanitize: req.sanitize_profile === "partner-share-default",
      });
      const bytes = encodeBundle(payload);
      this.lastExportedBundle = bytes;
      return {
        status: 200,
        contentType: "application/gzip",
        headers: {
          "Content-Disposition": 'attachment; filename="bundle.pmdf.tar.gz"',
        },
        body: bytes.toString("utf-8"),
      };
    }

    if (method === "POST" && pathname === "/bundles/import/validate") {
      let file = extractBundleBytesFromMultipart(multipartData, contentType);
      if ((!file || file.length === 0) && this.lastExportedBundle) {
        file = this.lastExportedBundle;
      }
      if (!file) {
        return json(422, { detail: "file が必要です" });
      }
      const bundle = decodeBundle(file);
      const diffs = bundle.entities.map((entity) => ({
        id: entity.id,
        kind: entity.kind,
        diff_type: "new",
        field_diffs: {},
        reference_errors: [],
      }));
      return json(200, {
        is_valid: true,
        manifest: { attachment_count: Object.keys(bundle.attachments).length },
        diffs,
      });
    }

    if (method === "POST" && pathname === "/bundles/import/apply") {
      let file = extractBundleBytesFromMultipart(multipartData, contentType);
      if ((!file || file.length === 0) && this.lastExportedBundle) {
        file = this.lastExportedBundle;
      }
      if (!file) {
        return json(422, { detail: "file が必要です" });
      }
      const bundle = decodeBundle(file);
      const applied: string[] = [];
      for (const entity of bundle.entities) {
        const kind = String(entity.kind);
        const id = String(entity.id);
        if (!this.secondaryEntities[kind]) {
          this.secondaryEntities[kind] = {};
        }
        this.secondaryEntities[kind][id] = entity;
        applied.push(id);
      }
      return json(200, { applied_ids: applied, skipped_ids: [], dry_run: false });
    }

    return null;
  }
}

export async function fulfillRoute(route: Route, backend: MockPdmBackend): Promise<void> {
  const request = route.request();
  const url = new URL(request.url());
  const pathname = url.pathname.replace(/\/$/, "") || "/";
  let body: unknown = undefined;
  const multipartData = request.postDataBuffer();
  const contentType = request.headers()["content-type"];
  if (
    request.method() !== "GET" &&
    request.method() !== "HEAD" &&
    !(contentType?.includes("multipart/form-data"))
  ) {
    try {
      body = request.postDataJSON();
    } catch {
      body = undefined;
    }
  }
  const result = backend.handle(
    request.method(),
    pathname,
    url.searchParams,
    body,
    multipartData,
    contentType,
  );
  if (result) {
    await route.fulfill(result);
    return;
  }
  await route.fulfill({
    status: 404,
    contentType: "application/json",
    body: JSON.stringify({ detail: `mock: unhandled ${request.method()} ${pathname}` }),
  });
}
