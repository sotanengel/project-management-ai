import { expect, test } from "@playwright/test";
import {
  installMockBackend,
  loginAsAdmin,
  mockApiPost,
  sendChatInstruction,
  spaNavigate,
} from "./helpers/setup";
import {
  DECISION_ID,
  PRODUCT_ID,
  RELEASE_ID,
  ROADMAP_ID,
  STAKEHOLDER_ID,
} from "./helpers/seed-entities";

/**
 * AC-06 補完: 承認レコードなしでは L1 実行系 API が 403 となることを UI セッション上で検証する。
 * (実行系ボタンが未実装のエンドポイントはブラウザ fetch + route モックで代替)
 */
test.describe("approval bypass blocked (AC-06)", () => {
  test.setTimeout(60_000);

  test.beforeEach(async ({ page }) => {
    await installMockBackend(page);
    await loginAsAdmin(page);
  });

  test("未承認のまま L1 実行 API を叩くと 403 が返る", async ({ page }) => {
    const roadmap = await mockApiPost(page, `/roadmap/${ROADMAP_ID}/confirm`);
    expect(roadmap.status).toBe(403);
    const roadmapBody = roadmap.body as { detail?: string };
    expect(roadmapBody.detail).toMatch(/承認/);

    const release = await mockApiPost(page, `/release/${RELEASE_ID}/go-no-go`);
    expect(release.status).toBe(403);

    const decision = await mockApiPost(
      page,
      `/pmdf/decision/${DECISION_ID}/execute`,
    );
    expect(decision.status).toBe(403);

    const stakeholder = await mockApiPost(
      page,
      `/stakeholder/${STAKEHOLDER_ID}/send-message`,
    );
    expect(stakeholder.status).toBe(403);
  });

  test("承認キューに未処理起案がある間は L1 実行はブロックされたまま", async ({
    page,
  }) => {
    await sendChatInstruction(page, "ビジョンを更新");

    await spaNavigate(page, "/approvals");
    await expect(page.getByText(`対象: ${PRODUCT_ID}`)).toBeVisible();

    const blocked = await mockApiPost(page, `/roadmap/${ROADMAP_ID}/confirm`);
    expect(blocked.status).toBe(403);
  });
});
