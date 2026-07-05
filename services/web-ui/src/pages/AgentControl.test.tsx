import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { http, HttpResponse } from "msw";
import { server } from "../test/server";
import { API_BASE_URL } from "../api/client";
import { MockWebSocket } from "../test/mockWebSocket";
import { AuthContext } from "../auth/AuthContext";
import { AppStateProvider } from "../state/AppStateContext";
import { AgentControl } from "./AgentControl";

const ADMIN_TOKEN =
  "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9." +
  "eyJyb2xlIjoiYWRtaW4ifQ.signature";

const PRODUCTS = [{ kind: "product", id: "product-01", name: "PdM AI" }];

const AUTONOMY = [
  {
    product_id: "product-01",
    business_function: "backlog",
    level: "L1",
  },
];

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <AuthContext.Provider
      value={{
        token: ADMIN_TOKEN,
        isAuthenticated: true,
        login: vi.fn(),
        logout: vi.fn(),
      }}
    >
      <AppStateProvider>
        <QueryClientProvider client={queryClient}>
          <MemoryRouter>
            <AgentControl />
          </MemoryRouter>
        </QueryClientProvider>
      </AppStateProvider>
    </AuthContext.Provider>,
  );
}

describe("AgentControl", () => {
  beforeEach(() => {
    MockWebSocket.reset();
    vi.stubGlobal("WebSocket", MockWebSocket);
    server.use(
      http.get(`${API_BASE_URL}/pmdf/product`, () =>
        HttpResponse.json(PRODUCTS),
      ),
      http.get(`${API_BASE_URL}/autonomy`, () => HttpResponse.json(AUTONOMY)),
      http.get(`${API_BASE_URL}/autonomy/emergency-stop/status`, () =>
        HttpResponse.json({ emergency_stopped: false }),
      ),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("自律レベルマトリクスに現在値が表示され、変更でPUTが呼ばれる", async () => {
    let putCalled = false;
    server.use(
      http.put(
        `${API_BASE_URL}/autonomy/product-01/roadmap`,
        async ({ request }) => {
          const body = (await request.json()) as { level: string };
          expect(body.level).toBe("L2");
          putCalled = true;
          return HttpResponse.json({
            product_id: "product-01",
            business_function: "roadmap",
            level: "L2",
          });
        },
      ),
    );

    const user = userEvent.setup();
    renderPage();

    await waitFor(() => {
      expect(screen.getByLabelText("product-01 roadmap")).toBeInTheDocument();
    });

    const select = screen.getByLabelText("product-01 roadmap");
    expect(select).toHaveValue("L0");

    await user.selectOptions(select, "L2");

    await waitFor(() => {
      expect(putCalled).toBe(true);
    });
  });

  it("チャット指示送信後、WebSocketで実行状況が更新される", async () => {
    server.use(
      http.post(`${API_BASE_URL}/chat/instructions`, async ({ request }) => {
        const body = (await request.json()) as {
          message: string;
          product_id: string;
        };
        expect(body.message).toBe("バックログを整理して");
        expect(body.product_id).toBe("product-01");
        return HttpResponse.json(
          {
            id: "task-99",
            message: body.message,
            product_id: body.product_id,
            actor: "user:1",
            status: "pending",
          },
          { status: 201 },
        );
      }),
    );

    const user = userEvent.setup();
    renderPage();

    await waitFor(() => {
      expect(MockWebSocket.instances.length).toBeGreaterThan(0);
    });

    const ws = MockWebSocket.instances[0];
    act(() => {
      ws.simulateOpen();
    });

    await user.type(
      screen.getByLabelText("指示メッセージ"),
      "バックログを整理して",
    );
    await user.selectOptions(screen.getByLabelText("プロダクト"), "product-01");
    await user.click(screen.getByRole("button", { name: "指示を送信" }));

    await waitFor(() => {
      expect(screen.getByTestId("chat-task-status")).toHaveTextContent(
        "受付済み",
      );
    });

    act(() => {
      ws.simulateMessage({
        type: "agent.activity",
        data: {
          task_id: "task-99",
          status: "running",
          product_id: "product-01",
        },
      });
    });

    await waitFor(() => {
      expect(screen.getByTestId("chat-task-status")).toHaveTextContent(
        "実行中",
      );
    });
  });

  it("緊急停止ボタンが確認ダイアログ後にPOSTし、停止中バナーを表示する", async () => {
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);
    let stopCalled = false;
    server.use(
      http.post(`${API_BASE_URL}/autonomy/emergency-stop`, () => {
        stopCalled = true;
        return HttpResponse.json({ emergency_stopped: true });
      }),
    );

    const user = userEvent.setup();
    renderPage();

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: "緊急停止" }),
      ).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: "緊急停止" }));

    expect(confirmSpy).toHaveBeenCalled();
    await waitFor(() => {
      expect(stopCalled).toBe(true);
      expect(screen.getByTestId("emergency-stop-banner")).toBeInTheDocument();
    });
  });
});
