import { expect, test } from "@playwright/test";
import {
  approveFirstProposal,
  installMockBackend,
  loginAsAdmin,
  mockApiPost,
  openDocumentEntity,
  openEntityEditor,
  sendChatInstruction,
  spaNavigate,
} from "./helpers/setup";
import {
  DECISION_ID,
  EXPERIMENT_ID,
  PRODUCT_ID,
  RELEASE_ID,
  ROADMAP_ID,
  STORY_ID,
} from "./helpers/seed-entities";

/**
 * AC-05: FR-PD-01〜11 相当の業務フローをモックバックエンド上で UI 経由一巡する。
 */
test.describe("full PDM cycle (AC-05)", () => {
  test.setTimeout(90_000);

  test.beforeEach(async ({ page }) => {
    await installMockBackend(page);
    await loginAsAdmin(page);
  });

  test("ビジョン→ロードマップ→バックログ→実験→リリース→DR→週次レビューを一巡する", async ({
    page,
  }) => {
    // 1. ビジョン更新起案 → 承認 → product.vision 反映
    await test.step("ビジョン更新(L1)", async () => {
      await sendChatInstruction(page, "ビジョンを更新してください");
      await approveFirstProposal(page);
      await openDocumentEntity(page, "product", PRODUCT_ID);
      await expect(page.getByText("ゲストにも安心な購買体験を届ける")).toBeVisible();
    });

    // 2. ロードマップ更新 → 承認 → L1確定API
    await test.step("ロードマップ更新(L1)", async () => {
      await sendChatInstruction(page, "ロードマップを更新");
      await approveFirstProposal(page);
      const confirm = await mockApiPost(
        page,
        `/roadmap/${ROADMAP_ID}/confirm`,
      );
      expect(confirm.status).toBe(200);
      await openDocumentEntity(page, "roadmap_item", ROADMAP_ID);
      await expect(page.getByText("committed")).toBeVisible();
    });

    // 3. バックログ運用(L2) — story を即時更新
    await test.step("バックログ運用(L2)", async () => {
      await openEntityEditor(page, "story", STORY_ID);
      await page.getByLabel("ステータス").fill("in_progress");
      await page.getByRole("button", { name: "保存" }).click();
      await expect(page.getByTestId("entity-editor-success")).toBeVisible();
      await openDocumentEntity(page, "story", STORY_ID);
      await expect(page.getByText("in_progress")).toBeVisible();
    });

    // 4. 実験管理 — 結果記録
    await test.step("実験管理(L2)", async () => {
      await openEntityEditor(page, "experiment", EXPERIMENT_ID);
      await page.getByRole("button", { name: "YAML/JSONエディタ" }).click();
      const editor = page.locator("textarea").first();
      const current = await editor.inputValue();
      const parsed = JSON.parse(current) as Record<string, unknown>;
      parsed.status = "completed";
      parsed.results = "再訪率 +6pt";
      await editor.fill(JSON.stringify(parsed, null, 2));
      await page.getByRole("button", { name: "保存" }).click();
      await expect(page.getByTestId("entity-editor-success")).toBeVisible();
    });

    // 5. リリース判断 → 承認 → go/no-go
    await test.step("リリース判断(L1)", async () => {
      await sendChatInstruction(page, "リリース判断を起案");
      await approveFirstProposal(page);
      const go = await mockApiPost(page, `/release/${RELEASE_ID}/go-no-go`);
      expect(go.status).toBe(200);
    });

    // 6. Decision Record (L3) — 承認不要で記録済み
    await test.step("Decision Record(L3)", async () => {
      await openDocumentEntity(page, "decision", DECISION_ID);
      await expect(page.getByText("メールリンク方式").first()).toBeVisible();
      const exec = await mockApiPost(
        page,
        `/pmdf/decision/${DECISION_ID}/execute`,
      );
      expect([200, 403]).toContain(exec.status);
    });

    // 7. 週次レビュー起案 → 承認キューに表示
    await test.step("週次レビュー(L1)", async () => {
      await sendChatInstruction(page, "週次レビューを実施");
      await spaNavigate(page, "/approvals");
      await expect(page.getByText("report-01JZX5WWWW01BBBBCCCCDDDDAB")).toBeVisible();
    });
  });
});
