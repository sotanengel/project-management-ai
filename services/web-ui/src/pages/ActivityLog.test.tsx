import { describe, expect, it } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { http, HttpResponse } from "msw";
import { server } from "../test/server";
import { API_BASE_URL } from "../api/client";
import { ActivityLog } from "./ActivityLog";

const TASKS = [
  {
    id: "chat-task-2",
    message: "ロードマップを見直して",
    product_id: "prod-01",
    actor: "user:editor",
    status: "running",
    result: null,
    error: null,
    intent: "vision_roadmap_release",
  },
  {
    id: "chat-task-1",
    message: "バックログを整理して",
    product_id: "prod-01",
    actor: "user:editor",
    status: "done",
    result: {
      model: "pdm-main",
      x_evidence: [{ source: "data", description: "RICE入力値", data: {} }],
    },
    error: null,
    intent: "backlog",
  },
];

const AUDIT_RECORDS = [
  {
    timestamp: "2026-07-01T00:00:00Z",
    actor: "user:editor",
    action: "pmdf.story.create",
    target_kind: "story",
    target_id: "story-01",
    detail: {},
    prev_hash: null,
    hash: "abc",
  },
];

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <ActivityLog />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("ActivityLog", () => {
  it("実行中/完了タスクをステータス別に表示する", async () => {
    server.use(
      http.get(`${API_BASE_URL}/chat/tasks`, () => HttpResponse.json(TASKS)),
      http.get(`${API_BASE_URL}/audit/records`, () =>
        HttpResponse.json(AUDIT_RECORDS),
      ),
    );

    renderPage();

    await waitFor(() => {
      expect(screen.getByText("ロードマップを見直して")).toBeInTheDocument();
    });
    expect(screen.getByText("バックログを整理して")).toBeInTheDocument();
    expect(screen.getByText(/実行中/)).toBeInTheDocument();
    expect(screen.getByText(/完了/)).toBeInTheDocument();
  });

  it("タスク詳細を開くと使用モデルと根拠が表示される", async () => {
    server.use(
      http.get(`${API_BASE_URL}/chat/tasks`, () => HttpResponse.json(TASKS)),
      http.get(`${API_BASE_URL}/audit/records`, () =>
        HttpResponse.json(AUDIT_RECORDS),
      ),
    );
    const user = userEvent.setup();
    renderPage();

    await waitFor(() => {
      expect(screen.getByText("バックログを整理して")).toBeInTheDocument();
    });
    await user.click(screen.getByText("バックログを整理して"));

    await waitFor(() => {
      expect(screen.getByText("pdm-main")).toBeInTheDocument();
    });
    expect(screen.getByText(/データ根拠/)).toBeInTheDocument();
  });

  it("監査ログ検索フィルタで絞り込んだ結果が表示される", async () => {
    server.use(
      http.get(`${API_BASE_URL}/chat/tasks`, () => HttpResponse.json([])),
      http.get(`${API_BASE_URL}/audit/records`, ({ request }) => {
        const url = new URL(request.url);
        if (url.searchParams.get("actor") === "user:editor") {
          return HttpResponse.json(AUDIT_RECORDS);
        }
        return HttpResponse.json([]);
      }),
    );
    const user = userEvent.setup();
    renderPage();

    await waitFor(() => {
      expect(screen.getByText("監査ログ")).toBeInTheDocument();
    });
    await user.type(screen.getByLabelText("actor"), "user:editor");
    await user.click(screen.getByRole("button", { name: "検索" }));

    await waitFor(() => {
      expect(screen.getByText("pmdf.story.create")).toBeInTheDocument();
    });
  });
});
