import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { AppStateContext } from "../state/AppStateContext";
import { ApprovalBadge } from "./ApprovalBadge";

function renderWithCount(count: number) {
  return render(
    <AppStateContext.Provider
      value={{
        pendingApprovalCount: count,
        isWsConnected: true,
        recentActivity: [],
      }}
    >
      <ApprovalBadge />
    </AppStateContext.Provider>,
  );
}

describe("ApprovalBadge", () => {
  it("承認待ち件数が0件の場合はバッジを表示しない", () => {
    renderWithCount(0);
    expect(screen.queryByTestId("approval-badge")).not.toBeInTheDocument();
  });

  it("承認待ち件数を表示する", () => {
    renderWithCount(5);
    expect(screen.getByTestId("approval-badge")).toHaveTextContent("5");
  });

  it("件数が変化すると表示も更新される", () => {
    const { rerender } = render(
      <AppStateContext.Provider
        value={{
          pendingApprovalCount: 2,
          isWsConnected: true,
          recentActivity: [],
        }}
      >
        <ApprovalBadge />
      </AppStateContext.Provider>,
    );
    expect(screen.getByTestId("approval-badge")).toHaveTextContent("2");

    rerender(
      <AppStateContext.Provider
        value={{
          pendingApprovalCount: 7,
          isWsConnected: true,
          recentActivity: [],
        }}
      >
        <ApprovalBadge />
      </AppStateContext.Provider>,
    );
    expect(screen.getByTestId("approval-badge")).toHaveTextContent("7");
  });
});
