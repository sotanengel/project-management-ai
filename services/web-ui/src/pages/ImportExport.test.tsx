import { describe, expect, it } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import { server } from "../test/server";
import { API_BASE_URL } from "../api/client";
import { ImportExport } from "./ImportExport";

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <ImportExport />
    </QueryClientProvider>,
  );
}

describe("ImportExport", () => {
  it("エクスポートフォームでプロダクト/種別を指定するとPOST /bundles/exportが呼ばれる", async () => {
    let capturedBody: unknown = null;
    server.use(
      http.post(`${API_BASE_URL}/bundles/export`, async ({ request }) => {
        capturedBody = await request.json();
        return new HttpResponse(new Blob(["dummy"]), {
          headers: { "Content-Type": "application/gzip" },
        });
      }),
    );

    // jsdomにはURL.createObjectURLが無いためスタブする
    URL.createObjectURL = () => "blob:mock-url";
    URL.revokeObjectURL = () => undefined;

    const user = userEvent.setup();
    renderPage();

    await user.type(
      screen.getByLabelText("プロダクトID(カンマ区切り)"),
      "prod-01",
    );
    await user.type(
      screen.getByLabelText("種別(カンマ区切り)"),
      "story,decision",
    );
    await user.click(screen.getByRole("button", { name: "エクスポート" }));

    await waitFor(() => {
      expect(capturedBody).toEqual({
        product_ids: ["prod-01"],
        kinds: ["story", "decision"],
      });
    });
  });

  it("バンドルアップロード後、conflict種別のエンティティが一覧表示され取込側/既存側を選択できる", async () => {
    server.use(
      http.post(`${API_BASE_URL}/bundles/import/validate`, () =>
        HttpResponse.json({
          is_valid: true,
          manifest: {},
          diffs: [
            {
              id: "story-01",
              kind: "story",
              diff_type: "conflict",
              field_diffs: {
                title: { current: "既存", incoming: "取込" },
              },
              reference_errors: [],
            },
            {
              id: "story-02",
              kind: "story",
              diff_type: "new",
              field_diffs: {},
              reference_errors: [],
            },
          ],
        }),
      ),
    );

    const user = userEvent.setup();
    renderPage();

    const file = new File(["dummy"], "bundle.pmdf.tar.gz", {
      type: "application/gzip",
    });
    const fileInput = screen.getByLabelText("バンドルファイル");
    await user.upload(fileInput, file);
    await user.click(screen.getByRole("button", { name: "プレビュー" }));

    await waitFor(() => {
      expect(screen.getAllByText(/story-01/).length).toBeGreaterThan(0);
    });

    const conflictSection = screen.getByTestId("conflict-resolver");
    await user.click(
      within(conflictSection).getByRole("button", { name: "取込側を採用" }),
    );

    expect(screen.getByRole("button", { name: "適用" })).toBeEnabled();
  });

  it("適用(apply)完了後、成功メッセージと適用件数が表示される", async () => {
    server.use(
      http.post(`${API_BASE_URL}/bundles/import/validate`, () =>
        HttpResponse.json({
          is_valid: true,
          manifest: {},
          diffs: [
            {
              id: "story-02",
              kind: "story",
              diff_type: "new",
              field_diffs: {},
              reference_errors: [],
            },
          ],
        }),
      ),
      http.post(`${API_BASE_URL}/bundles/import/apply`, () =>
        HttpResponse.json({
          applied_ids: ["story-02"],
          skipped_ids: [],
          dry_run: false,
        }),
      ),
    );

    const user = userEvent.setup();
    renderPage();

    const file = new File(["dummy"], "bundle.pmdf.tar.gz", {
      type: "application/gzip",
    });
    const fileInput = screen.getByLabelText("バンドルファイル");
    await user.upload(fileInput, file);
    await user.click(screen.getByRole("button", { name: "プレビュー" }));

    await waitFor(() => {
      expect(screen.getByText(/story-02/)).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: "適用" }));

    await waitFor(() => {
      expect(screen.getByTestId("import-apply-success")).toHaveTextContent("1");
    });
  });
});
