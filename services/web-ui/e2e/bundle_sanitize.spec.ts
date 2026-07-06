import { expect, test } from "@playwright/test";
import { ADMIN_TOKEN } from "./helpers/jwt";
import { API_BASE, installMockBackend, loginAsAdmin } from "./helpers/setup";
import { decodeBundle, MASKED } from "./helpers/bundle-mock";
import { DECISION_ID, STAKEHOLDER_ID, STORY_ID } from "./helpers/seed-entities";

/** AC-08: 共有プロファイル指定エクスポートで機微フィールドがマスキングされる。 */
test.describe("bundle sanitize (AC-08)", () => {
  test("partner-share-default プロファイルで個人名・内部指標がマスクされる", async ({
    page,
  }) => {
    await installMockBackend(page);
    await loginAsAdmin(page);

    const bundleBytes = await page.evaluate(
      async ({ apiBase, authToken }) => {
        const response = await fetch(`${apiBase}/bundles/export`, {
          method: "POST",
          headers: {
            Authorization: `Bearer ${authToken}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            sanitize_profile: "partner-share-default",
          }),
        });
        const buffer = await response.arrayBuffer();
        return Array.from(new Uint8Array(buffer));
      },
      { apiBase: API_BASE, authToken: ADMIN_TOKEN },
    );

    const payload = decodeBundle(Buffer.from(bundleBytes));
    expect(payload.sanitized).toBe(true);

    const story = payload.entities.find((e) => e.id === STORY_ID);
    expect(story).toBeTruthy();
    const storyPriority = story?.priority as Record<string, unknown>;
    expect(storyPriority.reach).toBe(MASKED);
    expect(story?.title).toBe("ゲスト購入でも注文履歴をメールから参照できる");

    const stakeholder = payload.entities.find((e) => e.id === STAKEHOLDER_ID);
    expect(stakeholder?.name).toBe(MASKED);
    const policy = stakeholder?.contact_policy as Record<string, unknown>;
    expect(policy.personal_name).toBe(MASKED);
    expect(policy.channel).toBe("email");

    const metric = payload.entities.find(
      (e) => e.id === "metric-01JZX0MMMM01BBBBCCCCDDDDEE",
    );
    if (metric && "current_value" in metric) {
      expect(metric.current_value).toBe(MASKED);
    }

    expect(
      payload.attachments[`${DECISION_ID}/guest-order-spec.pdf`],
    ).toBe(
      "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    );
  });
});
