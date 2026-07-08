import { expect, test, type Page } from "@playwright/test";

const API_BASE = "http://localhost:8000";

async function stubAuthenticatedApi(page: Page): Promise<void> {
  await page.route(`${API_BASE}/auth/login`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        access_token: "e2e.jwt.token",
        token_type: "bearer",
      }),
    });
  });

  await page.route(`${API_BASE}/approvals*`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([]),
    });
  });

  await page.route(`${API_BASE}/pmdf/roadmap_item`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([]),
    });
  });

  await page.route(`${API_BASE}/pmdf/metric`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([]),
    });
  });

  await page.route(`${API_BASE}/pmdf/product`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([
        { kind: "product", id: "product-01", name: "E2Eプロダクト" },
      ]),
    });
  });

  await page.route(
    `${API_BASE}/autonomy/emergency-stop/status`,
    async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ emergency_stopped: false }),
      });
    },
  );

  await page.route(`${API_BASE}/autonomy`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([
        {
          product_id: "product-01",
          business_function: "backlog",
          level: "L1",
        },
      ]),
    });
  });

  await page.route(`${API_BASE}/costs/summary`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        period: "2026-07",
        budget_monthly_jpy: 50000,
        total_spend_jpy: 25000,
        consumption_ratio: 0.5,
        budget_status: "ok",
        by_model: [],
        by_logical_name: [],
        by_day: [],
      }),
    });
  });
}

async function login(page: Page): Promise<void> {
  await page.goto("/login");
  await page.getByLabel("メールアドレス").fill("pm@example.com");
  await page.getByLabel("パスワード").fill("correct-horse-battery-staple");
  await page.getByRole("button", { name: "ログイン" }).click();
  await expect(page).toHaveURL(/\/dashboard/);
}

async function assertNoHorizontalOverflow(page: Page): Promise<void> {
  const overflow = await page.evaluate(() => {
    const doc = document.documentElement;
    return doc.scrollWidth > doc.clientWidth + 1;
  });
  expect(overflow).toBe(false);
}

test.describe("レスポンシブレイアウト(FR-UI-10)", () => {
  test.beforeEach(async ({ page }) => {
    await stubAuthenticatedApi(page);
    await login(page);
  });

  test("エージェント制御画面がビューポート内に収まる", async ({ page }) => {
    await page.getByRole("link", { name: /エージェント制御/ }).click();
    await expect(page).toHaveURL(/\/agent-control/);
    await expect(
      page.getByRole("heading", { name: "エージェント制御" }),
    ).toBeVisible();
    await expect(page.getByTestId("autonomy-matrix")).toBeVisible();
    await expect(page.getByRole("navigation")).toBeVisible();
    await assertNoHorizontalOverflow(page);
  });

  test("コスト画面がビューポート内に収まる", async ({ page }) => {
    await page.getByRole("link", { name: /^コスト$/ }).click();
    await expect(page).toHaveURL(/\/costs/);
    await expect(
      page.getByRole("heading", { name: "コスト / 学習状況" }),
    ).toBeVisible();
    await expect(page.getByTestId("cost-progress-bar")).toBeVisible();
    await expect(page.getByTestId("learning-status")).toBeVisible();
    await expect(page.getByRole("navigation")).toBeVisible();
    await assertNoHorizontalOverflow(page);
  });
});
