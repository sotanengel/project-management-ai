import { describe, expect, it } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import { server } from "../test/server";
import { API_BASE_URL } from "../api/client";
import { ApprovalHistory } from "./ApprovalHistory";

const DECIDED_PROPOSALS = [
  {
    id: "proposal-01",
    target: "roadmap-01",
    proposer: "stakeholder-01",
    status: "approved",
    approver: "stakeholder-02",
    reason: "問題なし",
    approval_entity_id: "approval-01",
    draft: null,
  },
  {
    id: "proposal-02",
    target: "dec-01",
    proposer: "stakeholder-01",
    status: "rejected",
    approver: "stakeholder-02",
    reason: "根拠不足のため差し戻し",
    approval_entity_id: "approval-02",
    draft: null,
  },
];

function renderHistory() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <ApprovalHistory />
    </QueryClientProvider>,
  );
}

describe("ApprovalHistory", () => {
  it("過去の承認/差し戻し判断と理由を表示する", async () => {
    server.use(
      http.get(`${API_BASE_URL}/approvals`, () =>
        HttpResponse.json(DECIDED_PROPOSALS),
      ),
    );

    renderHistory();

    await waitFor(() => {
      expect(screen.getByText("問題なし")).toBeInTheDocument();
    });
    expect(screen.getByText("根拠不足のため差し戻し")).toBeInTheDocument();
    expect(screen.getAllByText(/承認済み|差し戻し/).length).toBeGreaterThan(0);
  });

  it("履歴が0件の場合はその旨を表示する", async () => {
    server.use(
      http.get(`${API_BASE_URL}/approvals`, () => HttpResponse.json([])),
    );

    renderHistory();

    await waitFor(() => {
      expect(screen.getByText("承認履歴はまだありません")).toBeInTheDocument();
    });
  });
});
