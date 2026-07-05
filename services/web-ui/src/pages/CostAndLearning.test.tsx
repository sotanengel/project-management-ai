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

describe("CostAndLearning", () => {
  it("コスト消化率をプログレスバーで表示する", async () => {
    server.use(
      http.get(`${API_BASE_URL}/costs/summary`, () =>
        HttpResponse.json(SUMMARY_OK),
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
    );

    renderPage();

    await waitFor(() => {
      expect(screen.getByTestId("cost-progress-bar")).toHaveAttribute(
        "data-status",
        "warning",
      );
    });
  });

  it("学習進捗プレースホルダが表示される", async () => {
    server.use(
      http.get(`${API_BASE_URL}/costs/summary`, () =>
        HttpResponse.json(SUMMARY_OK),
      ),
    );

    renderPage();

    await waitFor(() => {
      expect(screen.getByTestId("learning-placeholder")).toBeInTheDocument();
    });
    expect(screen.getByTestId("learning-placeholder")).toHaveTextContent(
      /E8/,
    );
  });
});
