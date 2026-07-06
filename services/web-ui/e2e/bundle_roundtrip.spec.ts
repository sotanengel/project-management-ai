import { expect, test } from "@playwright/test";
import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";
import { ADMIN_TOKEN } from "./helpers/jwt";
import {
  API_BASE,
  installMockBackend,
  loginAsAdmin,
  spaNavigate,
} from "./helpers/setup";
import { DECISION_ID } from "./helpers/seed-entities";

/** AC-07: Export→空ストアへ Import でエンティティ・添付ハッシュが一致する。 */
test.describe("bundle roundtrip (AC-07)", () => {
  test("Import/Export UI 経由でバンドル往復する", async ({ page }) => {
    const backend = await installMockBackend(page);
    backend.resetSecondaryStore();
    await loginAsAdmin(page);
    await spaNavigate(page, "/import-export");

    const bundleBase64 = await page.evaluate(
      async ({ apiBase, authToken }) => {
        const response = await fetch(`${apiBase}/bundles/export`, {
          method: "POST",
          headers: {
            Authorization: `Bearer ${authToken}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({}),
        });
        const buffer = await response.arrayBuffer();
        const bytes = new Uint8Array(buffer);
        let binary = "";
        for (const byte of bytes) {
          binary += String.fromCharCode(byte);
        }
        return btoa(binary);
      },
      { apiBase: API_BASE, authToken: ADMIN_TOKEN },
    );

    const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "pmdf-e2e-"));
    const bundlePath = path.join(tmpDir, "bundle.pmdf.tar.gz");
    fs.writeFileSync(bundlePath, Buffer.from(bundleBase64, "base64"));

    await page.locator("#import-file").setInputFiles(bundlePath);
    await page.getByRole("button", { name: "プレビュー" }).click();
    await expect(page.getByText(`decision/${DECISION_ID}: new`)).toBeVisible();

    await page.getByRole("button", { name: "適用" }).click();
    await expect(page.getByTestId("import-apply-success")).toBeVisible();
    expect(backend.bundleMatchesPrimary()).toBe(true);
  });
});
