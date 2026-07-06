import { expect, type Page } from "@playwright/test";
import { ADMIN_TOKEN } from "./jwt";
import { MockPdmBackend, fulfillRoute } from "./mock-backend";
import { PRODUCT_ID } from "./seed-entities";

export const API_BASE = "http://localhost:8000";

export async function installMockBackend(page: Page): Promise<MockPdmBackend> {
  const backend = new MockPdmBackend();

  await page.route(`${API_BASE}/**`, async (route) => {
    const url = route.request().url();
    if (url.includes("/auth/login")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          access_token: ADMIN_TOKEN,
          token_type: "bearer",
        }),
      });
      return;
    }
    if (url.includes("/auth/refresh")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          access_token: ADMIN_TOKEN,
          token_type: "bearer",
        }),
      });
      return;
    }
    await fulfillRoute(route, backend);
  });

  return backend;
}

export async function loginAsAdmin(page: Page): Promise<void> {
  await page.goto("/login");
  await page.getByLabel("メールアドレス").fill("pm@example.com");
  await page.getByLabel("パスワード").fill("correct-horse-battery-staple");
  await page.getByRole("button", { name: "ログイン" }).click();
  await page.waitForURL(/\/dashboard/);
}

/** JWT はメモリのみのため、ログイン後の遷移は SPA 内リンクを使う(full reload 禁止)。 */
export async function spaNavigate(page: Page, path: string): Promise<void> {
  const clicked = await page.evaluate((targetPath) => {
    const anchor = document.querySelector(`a[href="${targetPath}"]`);
    if (anchor instanceof HTMLElement) {
      anchor.click();
      return true;
    }
    return false;
  }, path);
  if (!clicked) {
    await page.evaluate((targetPath) => {
      window.history.pushState({}, "", targetPath);
      window.dispatchEvent(new PopStateEvent("popstate"));
    }, path);
  }
  await page.waitForURL(new RegExp(`${path.replace(/\//g, "\\/")}(\\?.*)?$`));
}

export async function approveFirstProposal(page: Page): Promise<void> {
  await spaNavigate(page, "/approvals");
  await page.getByRole("button", { name: "詳細" }).first().click();
  page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "承認" }).click();
}

export async function postChatInstruction(page: Page, message: string): Promise<void> {
  await page.evaluate(
    async ({ apiBase, authToken, productId, msg }) => {
      await fetch(`${apiBase}/chat/instructions`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${authToken}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ message: msg, product_id: productId }),
      });
    },
    {
      apiBase: API_BASE,
      authToken: ADMIN_TOKEN,
      productId: PRODUCT_ID,
      msg: message,
    },
  );
}

export async function sendChatInstruction(
  page: Page,
  message: string,
): Promise<void> {
  await spaNavigate(page, "/agent-control");
  await page.waitForURL(/\/agent-control/);
  await page.locator("#chat-product").waitFor({ state: "visible" });
  await page.locator("#chat-product").selectOption(PRODUCT_ID);
  await page.locator("#chat-message").fill(message);
  await page.getByRole("button", { name: "指示を送信" }).click();
}

/** page.route が効くブラウザ fetch 経由の API POST (page.request はルート対象外)。 */
export async function mockApiPost(
  page: Page,
  path: string,
  token: string = ADMIN_TOKEN,
): Promise<{ status: number; body: unknown }> {
  return page.evaluate(
    async ({ apiBase, apiPath, authToken }) => {
      const response = await fetch(`${apiBase}${apiPath}`, {
        method: "POST",
        headers: { Authorization: `Bearer ${authToken}` },
      });
      let body: unknown = null;
      try {
        body = await response.json();
      } catch {
        body = null;
      }
      return { status: response.status, body };
    },
    { apiBase: API_BASE, apiPath: path, authToken: token },
  );
}

export async function openDocumentEntity(
  page: Page,
  kind: string,
  id: string,
): Promise<void> {
  await spaNavigate(page, `/documents/${kind}/${id}`);
  await expect(page.getByTestId("entity-view")).toBeVisible();
}

export async function openEntityEditor(
  page: Page,
  kind: string,
  id: string,
): Promise<void> {
  await openDocumentEntity(page, kind, id);
  await page.getByRole("button", { name: "編集する" }).click();
  await page.waitForURL(new RegExp(`/edit/${kind}/${id}`));
}
