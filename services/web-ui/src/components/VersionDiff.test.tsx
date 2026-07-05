import { describe, expect, it } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import { server } from "../test/server";
import { API_BASE_URL } from "../api/client";
import { VersionDiff } from "./VersionDiff";

const HISTORY = [
  {
    commit_hash: "commit-2",
    author: "user:editor",
    committed_at: "2026-07-02T00:00:00Z",
    message: "update roadmap_item roadmap-01",
  },
  {
    commit_hash: "commit-1",
    author: "user:editor",
    committed_at: "2026-07-01T00:00:00Z",
    message: "create roadmap_item roadmap-01",
  },
];

function renderVersionDiff() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <VersionDiff kind="roadmap_item" entityId="roadmap-01" />
    </QueryClientProvider>,
  );
}

describe("VersionDiff", () => {
  it("版一覧を表示し、2版を選択するとdiffを表示する", async () => {
    server.use(
      http.get(`${API_BASE_URL}/pmdf/roadmap_item/roadmap-01/history`, () =>
        HttpResponse.json(HISTORY),
      ),
      http.get(
        `${API_BASE_URL}/pmdf/roadmap_item/roadmap-01`,
        ({ request }) => {
          const url = new URL(request.url);
          const ref = url.searchParams.get("ref");
          if (ref === "commit-1") {
            return HttpResponse.json({
              kind: "roadmap_item",
              id: "roadmap-01",
              theme: "旧テーマ",
              period: "2026-Q2",
              status: "planned",
            });
          }
          return HttpResponse.json({
            kind: "roadmap_item",
            id: "roadmap-01",
            theme: "新テーマ",
            period: "2026-Q3",
            status: "in_progress",
          });
        },
      ),
    );
    const user = userEvent.setup();
    renderVersionDiff();

    await waitFor(() => {
      expect(screen.getByTestId("version-select-from")).toBeInTheDocument();
    });

    await user.selectOptions(
      screen.getByTestId("version-select-from"),
      "commit-1",
    );
    await user.selectOptions(
      screen.getByTestId("version-select-to"),
      "commit-2",
    );

    await waitFor(() => {
      expect(screen.getByTestId("diff-field-theme")).toBeInTheDocument();
    });
    expect(screen.getByTestId("diff-field-theme")).toHaveTextContent(
      "旧テーマ",
    );
    expect(screen.getByTestId("diff-field-theme")).toHaveTextContent(
      "新テーマ",
    );
  });

  it("履歴が1件以下の場合は比較不可の旨を表示する", async () => {
    server.use(
      http.get(`${API_BASE_URL}/pmdf/roadmap_item/roadmap-01/history`, () =>
        HttpResponse.json([HISTORY[0]]),
      ),
    );

    renderVersionDiff();

    await waitFor(() => {
      expect(
        screen.getByText("比較できる版がまだありません"),
      ).toBeInTheDocument();
    });
  });
});
