import { describe, expect, it } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import { server } from "../test/server";
import { API_BASE_URL } from "../api/client";
import { AppStateContext } from "../state/AppStateContext";
import { Approvals } from "./Approvals";

const PENDING_PROPOSALS = [
  {
    id: "proposal-01",
    target: "roadmap-01HAPRAAAAAAAAAAAAAAAAAAAA",
    proposer: "stakeholder-01HAPRAAAAAAAAAAAAAAAAAAA",
    status: "proposed",
    approver: null,
    reason: null,
    approval_entity_id: null,
    draft: { theme: "新テーマ" },
  },
];

function renderApprovals() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <AppStateContext.Provider
        value={{
          pendingApprovalCount: 1,
          isWsConnected: true,
          recentActivity: [],
        }}
      >
        <Approvals />
      </AppStateContext.Provider>
    </QueryClientProvider>,
  );
}

describe("Approvals", () => {
  it("承認待ち一覧を表示する", async () => {
    server.use(
      http.get(`${API_BASE_URL}/approvals`, () =>
        HttpResponse.json(PENDING_PROPOSALS),
      ),
    );

    renderApprovals();

    await waitFor(() => {
      expect(
        screen.getByText(/roadmap-01HAPRAAAAAAAAAAAAAAAAAAAA/),
      ).toBeInTheDocument();
    });
  });

  it("項目を展開するとPMDF diffが表示される", async () => {
    server.use(
      http.get(`${API_BASE_URL}/approvals`, () =>
        HttpResponse.json(PENDING_PROPOSALS),
      ),
      http.get(
        `${API_BASE_URL}/pmdf/roadmap_item/roadmap-01HAPRAAAAAAAAAAAAAAAAAAAA`,
        () =>
          HttpResponse.json({
            kind: "roadmap_item",
            id: "roadmap-01HAPRAAAAAAAAAAAAAAAAAAAA",
            theme: "旧テーマ",
            period: "2026-Q3",
            status: "planned",
          }),
      ),
    );
    const user = userEvent.setup();
    renderApprovals();

    await waitFor(() => {
      expect(
        screen.getByText(/roadmap-01HAPRAAAAAAAAAAAAAAAAAAAA/),
      ).toBeInTheDocument();
    });
    await user.click(screen.getByRole("button", { name: /詳細/ }));

    await waitFor(() => {
      expect(screen.getByTestId("diff-field-theme")).toBeInTheDocument();
    });
  });

  it("承認待ちが0件の場合はその旨を表示する", async () => {
    server.use(
      http.get(`${API_BASE_URL}/approvals`, () => HttpResponse.json([])),
    );

    renderApprovals();

    await waitFor(() => {
      expect(
        screen.getByText("承認待ちの起案はありません"),
      ).toBeInTheDocument();
    });
  });
});
