import { describe, expect, it } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import { server } from "../test/server";
import { API_BASE_URL } from "../api/client";
import { AppStateContext } from "../state/AppStateContext";
import { Dashboard } from "./Dashboard";
import type { Metric, Product, RoadmapItem } from "../api/pmdfTypes";

const PRODUCTS: Product[] = [
  { kind: "product", id: "product-01", name: "サンプルプロダクト" },
];

const METRICS: Metric[] = [
  {
    kind: "metric",
    id: "metric-01",
    name: "週次アクティブ率",
    target_value: 0.6,
    threshold_value: 0.4,
    current_value: 0.5,
    time_series: [{ timestamp: "2026-06-01T00:00:00Z", value: 0.5 }],
  },
];

function makeRoadmapItems(count: number): RoadmapItem[] {
  return Array.from({ length: count }, (_, i) => ({
    kind: "roadmap_item",
    id: `roadmap-${i}`,
    product: "product-01",
    theme: `テーマ${i}`,
    period: "2026-Q3",
    status: i % 4 === 0 ? "done" : "planned",
  }));
}

function setupHandlers({ roadmapCount = 3 }: { roadmapCount?: number } = {}) {
  server.use(
    http.get(`${API_BASE_URL}/pmdf/product`, () => HttpResponse.json(PRODUCTS)),
    http.get(`${API_BASE_URL}/pmdf/metric`, () => HttpResponse.json(METRICS)),
    http.get(`${API_BASE_URL}/pmdf/roadmap_item`, () =>
      HttpResponse.json(makeRoadmapItems(roadmapCount)),
    ),
    http.get(`${API_BASE_URL}/approvals`, () =>
      HttpResponse.json([{ id: "p-1" }, { id: "p-2" }]),
    ),
  );
}

function renderDashboard() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <AppStateContext.Provider
        value={{
          pendingApprovalCount: 2,
          isWsConnected: true,
          recentActivity: [
            {
              task_id: "task-1",
              status: "done",
              intent: "backlog",
              product_id: "product-01",
            },
            {
              task_id: "task-2",
              status: "running",
              intent: "kpi_dr_review",
              product_id: "product-01",
            },
          ],
        }}
      >
        <Dashboard />
      </AppStateContext.Provider>
    </QueryClientProvider>,
  );
}

describe("Dashboard", () => {
  it("KPI推移・ロードマップ進捗・未承認件数・直近活動の4要素を表示する", async () => {
    setupHandlers();
    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText("週次アクティブ率")).toBeInTheDocument();
    });
    expect(
      screen.getByRole("heading", { name: "ロードマップ進捗" }),
    ).toBeInTheDocument();
    expect(screen.getByTestId("pending-approval-count")).toHaveTextContent("2");
    expect(
      screen.getByRole("heading", { name: "直近のエージェント活動" }),
    ).toBeInTheDocument();
    expect(screen.getByText("task-1")).toBeInTheDocument();
  });

  it("1万件相当のロードマップ項目でも仮想化リストのDOM行数が少数に留まる", async () => {
    setupHandlers({ roadmapCount: 10000 });
    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText("週次アクティブ率")).toBeInTheDocument();
    });

    const rows = screen.getAllByTestId("roadmap-item-row");
    expect(rows.length).toBeGreaterThan(0);
    expect(rows.length).toBeLessThan(200);
  });
});
