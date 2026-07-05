import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import { server } from "../test/server";
import { API_BASE_URL } from "../api/client";
import { ApprovalActionForm } from "./ApprovalActionForm";

function renderForm(onDecided = vi.fn()) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return {
    onDecided,
    ...render(
      <QueryClientProvider client={queryClient}>
        <ApprovalActionForm
          proposalId="proposal-01"
          approver="stakeholder-01HAPRAAAAAAAAAAAAAAAAAAA"
          onDecided={onDecided}
        />
      </QueryClientProvider>,
    ),
  };
}

describe("ApprovalActionForm", () => {
  it("承認ボタンで確認ダイアログ経由でdecide APIを呼ぶ", async () => {
    const user = userEvent.setup();
    let requestBody: unknown = null;
    server.use(
      http.post(
        `${API_BASE_URL}/approvals/proposal-01/decide`,
        async ({ request }) => {
          requestBody = await request.json();
          return HttpResponse.json({
            id: "proposal-01",
            target: "roadmap-01",
            proposer: "stakeholder-01",
            status: "approved",
            approver: "stakeholder-01HAPRAAAAAAAAAAAAAAAAAAA",
            reason: null,
            approval_entity_id: "approval-01",
            draft: null,
          });
        },
      ),
    );
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const { onDecided } = renderForm();

    await user.click(screen.getByRole("button", { name: "承認" }));

    expect(window.confirm).toHaveBeenCalled();
    await vi.waitFor(() => {
      expect(requestBody).toEqual({
        decision: "approved",
        approver: "stakeholder-01HAPRAAAAAAAAAAAAAAAAAAA",
        reason: "承認",
      });
    });
    await vi.waitFor(() => {
      expect(onDecided).toHaveBeenCalled();
    });
  });

  it("差し戻し時に理由未入力では送信ボタンが無効化される", async () => {
    renderForm();

    const rejectButton = screen.getByRole("button", { name: "差し戻し" });
    expect(rejectButton).toBeDisabled();
  });

  it("差し戻し理由を入力すると送信ボタンが有効化され、decide APIを呼ぶ", async () => {
    const user = userEvent.setup();
    let requestBody: unknown = null;
    server.use(
      http.post(
        `${API_BASE_URL}/approvals/proposal-01/decide`,
        async ({ request }) => {
          requestBody = await request.json();
          return HttpResponse.json({
            id: "proposal-01",
            target: "roadmap-01",
            proposer: "stakeholder-01",
            status: "rejected",
            approver: "stakeholder-01HAPRAAAAAAAAAAAAAAAAAAA",
            reason: "要件不足",
            approval_entity_id: "approval-01",
            draft: null,
          });
        },
      ),
    );
    const { onDecided } = renderForm();

    await user.type(screen.getByLabelText("差し戻し理由"), "要件不足のため");
    const rejectButton = screen.getByRole("button", { name: "差し戻し" });
    expect(rejectButton).toBeEnabled();
    await user.click(rejectButton);

    await vi.waitFor(() => {
      expect(requestBody).toEqual({
        decision: "rejected",
        approver: "stakeholder-01HAPRAAAAAAAAAAAAAAAAAAA",
        reason: "要件不足のため",
      });
    });
    await vi.waitFor(() => {
      expect(onDecided).toHaveBeenCalled();
    });
  });
});
