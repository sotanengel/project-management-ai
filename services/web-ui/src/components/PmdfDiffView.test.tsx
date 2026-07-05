import { describe, expect, it } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import { server } from "../test/server";
import { API_BASE_URL } from "../api/client";
import { PmdfDiffView } from "./PmdfDiffView";

const CURRENT_ENTITY = {
  kind: "roadmap_item",
  id: "roadmap-01HDIFFAAAAAAAAAAAAAAAAAAA",
  product: "prod-01HDIFFAAAAAAAAAAAAAAAAAAA",
  theme: "既存テーマ",
  period: "2026-Q3",
  status: "planned",
  objective: "obj-01HDIFFAAAAAAAAAAAAAAAAAAA",
};

function renderDiff(draft: Record<string, unknown> | null) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <PmdfDiffView
        kind="roadmap_item"
        entityId="roadmap-01HDIFFAAAAAAAAAAAAAAAAAAA"
        draft={draft}
      />
    </QueryClientProvider>,
  );
}

describe("PmdfDiffView", () => {
  it("変更されたフィールドを変更前後で表示する", async () => {
    server.use(
      http.get(
        `${API_BASE_URL}/pmdf/roadmap_item/roadmap-01HDIFFAAAAAAAAAAAAAAAAAAA`,
        () => HttpResponse.json(CURRENT_ENTITY),
      ),
    );

    renderDiff({ theme: "新しいテーマ", status: "in_progress" });

    await waitFor(() => {
      expect(screen.getByTestId("diff-field-theme")).toBeInTheDocument();
    });
    expect(screen.getByTestId("diff-field-theme")).toHaveTextContent(
      "既存テーマ",
    );
    expect(screen.getByTestId("diff-field-theme")).toHaveTextContent(
      "新しいテーマ",
    );
    expect(screen.getByTestId("diff-field-status")).toHaveTextContent(
      "planned",
    );
    expect(screen.getByTestId("diff-field-status")).toHaveTextContent(
      "in_progress",
    );
  });

  it("変更のないフィールドはdiff対象に含めない", async () => {
    server.use(
      http.get(
        `${API_BASE_URL}/pmdf/roadmap_item/roadmap-01HDIFFAAAAAAAAAAAAAAAAAAA`,
        () => HttpResponse.json(CURRENT_ENTITY),
      ),
    );

    renderDiff({ theme: "新しいテーマ" });

    await waitFor(() => {
      expect(screen.getByTestId("diff-field-theme")).toBeInTheDocument();
    });
    expect(screen.queryByTestId("diff-field-period")).not.toBeInTheDocument();
  });

  it("起案内容(draft)が無い場合は差分無し表示になる", async () => {
    server.use(
      http.get(
        `${API_BASE_URL}/pmdf/roadmap_item/roadmap-01HDIFFAAAAAAAAAAAAAAAAAAA`,
        () => HttpResponse.json(CURRENT_ENTITY),
      ),
    );

    renderDiff(null);

    await waitFor(() => {
      expect(screen.getByTestId("diff-empty")).toBeInTheDocument();
    });
  });

  it("対象エンティティが存在しない場合はエラー表示になる", async () => {
    server.use(
      http.get(
        `${API_BASE_URL}/pmdf/roadmap_item/roadmap-01HDIFFAAAAAAAAAAAAAAAAAAA`,
        () => HttpResponse.json({ detail: "見つかりません" }, { status: 404 }),
      ),
    );

    renderDiff({ theme: "新しいテーマ" });

    await waitFor(() => {
      expect(screen.getByTestId("diff-error")).toBeInTheDocument();
    });
  });
});
