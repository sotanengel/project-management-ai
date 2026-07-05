import { describe, expect, it } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { http, HttpResponse } from "msw";
import { server } from "../test/server";
import { API_BASE_URL } from "../api/client";
import { DocumentViewer } from "./DocumentViewer";

function renderViewer(initialPath = "/documents") {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialPath]}>
        <Routes>
          <Route path="/documents" element={<DocumentViewer />} />
          <Route path="/documents/:kind" element={<DocumentViewer />} />
          <Route path="/documents/:kind/:id" element={<DocumentViewer />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const STORY_ENTITY = {
  kind: "story",
  id: "story-01",
  title: "検索機能の改善",
  as_a: "ユーザーとして",
  i_want: "検索したい",
  so_that: "見つけたい",
  acceptance_criteria: [],
  priority: { method: "RICE" },
  status: "draft",
};

describe("DocumentViewer", () => {
  it("kind選択とエンティティ一覧から選択したエンティティを表示する", async () => {
    server.use(
      http.get(`${API_BASE_URL}/pmdf/story`, () =>
        HttpResponse.json([STORY_ENTITY]),
      ),
      http.get(`${API_BASE_URL}/pmdf/story/story-01`, () =>
        HttpResponse.json(STORY_ENTITY),
      ),
      http.get(`${API_BASE_URL}/pmdf/story/story-01/history`, () =>
        HttpResponse.json([
          {
            commit_hash: "commit-1",
            author: "user:editor",
            committed_at: "2026-07-01T00:00:00Z",
            message: "create story story-01",
          },
        ]),
      ),
    );
    const user = userEvent.setup();
    renderViewer();

    await user.selectOptions(screen.getByLabelText("種別"), "story");

    await waitFor(() => {
      expect(screen.getByText("検索機能の改善")).toBeInTheDocument();
    });
    await user.click(screen.getByText("検索機能の改善"));

    await waitFor(() => {
      expect(screen.getByTestId("entity-view")).toBeInTheDocument();
    });
  });

  it("存在しないエンティティを指定した場合はエラー表示になる", async () => {
    server.use(
      http.get(`${API_BASE_URL}/pmdf/story/story-missing`, () =>
        HttpResponse.json({ detail: "見つかりません" }, { status: 404 }),
      ),
    );

    renderViewer("/documents/story/story-missing");

    await waitFor(() => {
      expect(screen.getByTestId("document-viewer-error")).toBeInTheDocument();
    });
  });
});
