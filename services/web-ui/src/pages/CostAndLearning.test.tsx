import { describe, expect, it } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import { server } from "../test/server";
import { API_BASE_URL } from "../api/client";
import { CostAndLearning } from "./CostAndLearning";

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <CostAndLearning />
    </QueryClientProvider>,
  );
}

const SUMMARY_OK = {
  period: "2026-07",
  budget_monthly_jpy: 50000,
  total_spend_jpy: 20000,
  consumption_ratio: 0.4,
  budget_status: "ok",
  by_model: [],
  by_logical_name: [],
  by_day: [],
};

const LEARNING_STATUS_EMPTY = {
  has_activity: false,
  latest_job: null,
  gate_history: [],
};

describe("CostAndLearning", () => {
  it("コスト消化率をプログレスバーで表示する", async () => {
    server.use(
      http.get(`${API_BASE_URL}/costs/summary`, () =>
        HttpResponse.json(SUMMARY_OK),
      ),
      http.get(`${API_BASE_URL}/learning/status`, () =>
        HttpResponse.json(LEARNING_STATUS_EMPTY),
      ),
    );

    renderPage();

    await waitFor(() => {
      expect(screen.getByTestId("cost-progress-bar")).toBeInTheDocument();
    });
    expect(screen.getByTestId("cost-progress-bar")).toHaveAttribute(
      "data-status",
      "ok",
    );
    expect(screen.getByText(/20,000/)).toBeInTheDocument();
    expect(screen.getByText(/50,000/)).toBeInTheDocument();
  });

  it("80%超過でwarning、100%超過でexceededの視覚表示になる", async () => {
    server.use(
      http.get(`${API_BASE_URL}/costs/summary`, () =>
        HttpResponse.json({
          ...SUMMARY_OK,
          total_spend_jpy: 42000,
          consumption_ratio: 0.84,
          budget_status: "warning",
        }),
      ),
      http.get(`${API_BASE_URL}/learning/status`, () =>
        HttpResponse.json(LEARNING_STATUS_EMPTY),
      ),
    );

    renderPage();

    await waitFor(() => {
      expect(screen.getByTestId("cost-progress-bar")).toHaveAttribute(
        "data-status",
        "warning",
      );
    });
  });

  it("学習実績が無い場合は「学習実績なし」を表示し、プレースホルダは表示しない", async () => {
    server.use(
      http.get(`${API_BASE_URL}/costs/summary`, () =>
        HttpResponse.json(SUMMARY_OK),
      ),
      http.get(`${API_BASE_URL}/learning/status`, () =>
        HttpResponse.json(LEARNING_STATUS_EMPTY),
      ),
    );

    renderPage();

    await waitFor(() => {
      expect(screen.getByText("学習実績なし")).toBeInTheDocument();
    });
    expect(
      screen.queryByTestId("learning-placeholder"),
    ).not.toBeInTheDocument();
  });

  it("学習実績がある場合は直近ジョブと評価ゲート履歴を表示する", async () => {
    server.use(
      http.get(`${API_BASE_URL}/costs/summary`, () =>
        HttpResponse.json(SUMMARY_OK),
      ),
      http.get(`${API_BASE_URL}/learning/status`, () =>
        HttpResponse.json({
          has_activity: true,
          latest_job: {
            timestamp: "2026-07-02T00:00:00Z",
            job_type: "eval",
            status: "completed",
            metrics: { pdm_delta: 12.0 },
            decision: "promote",
          },
          gate_history: [
            {
              timestamp: "2026-07-02T00:00:00Z",
              job_type: "eval",
              status: "completed",
              metrics: { pdm_delta: 12.0 },
              decision: "promote",
            },
          ],
        }),
      ),
    );

    renderPage();

    await waitFor(() => {
      expect(screen.getByText(/eval/)).toBeInTheDocument();
    });
    expect(
      screen.queryByTestId("learning-placeholder"),
    ).not.toBeInTheDocument();
    expect(screen.getAllByText(/promote/).length).toBeGreaterThan(0);
  });
});
