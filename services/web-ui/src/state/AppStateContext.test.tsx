import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, render, screen } from "@testing-library/react";
import { useContext } from "react";
import { MockWebSocket } from "../test/mockWebSocket";
import { AppStateContext, AppStateProvider } from "./AppStateContext";
import { AuthContext } from "../auth/AuthContext";

function Probe() {
  const state = useContext(AppStateContext);
  if (!state) {
    throw new Error("no context");
  }
  return (
    <div>
      <span data-testid="pending-count">{state.pendingApprovalCount}</span>
      <span data-testid="ws-connected">{String(state.isWsConnected)}</span>
      <span data-testid="activity-count">{state.recentActivity.length}</span>
      {state.recentActivity[0] && (
        <span data-testid="latest-activity">
          {state.recentActivity[0].task_id}
        </span>
      )}
    </div>
  );
}

function renderWithToken(token: string | null) {
  return render(
    <AuthContext.Provider
      value={{
        token,
        isAuthenticated: token !== null,
        login: vi.fn(),
        logout: vi.fn(),
      }}
    >
      <AppStateProvider>
        <Probe />
      </AppStateProvider>
    </AuthContext.Provider>,
  );
}

describe("AppStateContext", () => {
  beforeEach(() => {
    MockWebSocket.reset();
    vi.stubGlobal("WebSocket", MockWebSocket);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("未認証(token無し)の場合はWebSocket接続を試みない", () => {
    renderWithToken(null);
    expect(MockWebSocket.instances).toHaveLength(0);
  });

  it("approval.count_changedイベントで承認待ち件数が更新される", () => {
    renderWithToken("test-token");
    const ws = MockWebSocket.instances[0];

    act(() => {
      ws.simulateOpen();
      ws.simulateMessage({
        type: "approval.count_changed",
        data: { count: 6 },
      });
    });

    expect(screen.getByTestId("pending-count")).toHaveTextContent("6");
    expect(screen.getByTestId("ws-connected")).toHaveTextContent("true");
  });

  it("agent.activityイベントを最新順に蓄積する", () => {
    renderWithToken("test-token");
    const ws = MockWebSocket.instances[0];

    act(() => {
      ws.simulateOpen();
      ws.simulateMessage({
        type: "agent.activity",
        data: {
          task_id: "task-1",
          status: "pending",
          product_id: "p1",
          intent: "backlog",
        },
      });
      ws.simulateMessage({
        type: "agent.activity",
        data: {
          task_id: "task-2",
          status: "running",
          product_id: "p1",
          intent: "backlog",
        },
      });
    });

    expect(screen.getByTestId("activity-count")).toHaveTextContent("2");
    expect(screen.getByTestId("latest-activity")).toHaveTextContent("task-2");
  });
});
