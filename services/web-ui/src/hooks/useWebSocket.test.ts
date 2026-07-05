import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, renderHook } from "@testing-library/react";
import { MockWebSocket } from "../test/mockWebSocket";
import { useWebSocket } from "./useWebSocket";

describe("useWebSocket", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    MockWebSocket.reset();
    vi.stubGlobal("WebSocket", MockWebSocket);
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("token未指定(未認証)の場合は接続を試みない", () => {
    renderHook(() => useWebSocket({ url: null, onMessage: vi.fn() }));
    expect(MockWebSocket.instances).toHaveLength(0);
  });

  it("urlが与えられると接続し、受信メッセージをonMessageへ渡す", async () => {
    const onMessage = vi.fn();
    renderHook(() =>
      useWebSocket({
        url: "ws://localhost:8000/ws/events?token=abc",
        onMessage,
      }),
    );

    expect(MockWebSocket.instances).toHaveLength(1);
    const ws = MockWebSocket.instances[0];

    act(() => {
      ws.simulateOpen();
      ws.simulateMessage({
        type: "approval.count_changed",
        data: { count: 3 },
      });
    });

    expect(onMessage).toHaveBeenCalledWith({
      type: "approval.count_changed",
      data: { count: 3 },
    });
  });

  it("切断時に指数バックオフで再接続を試みる(1秒→2秒→4秒)", async () => {
    const onMessage = vi.fn();
    renderHook(() =>
      useWebSocket({
        url: "ws://localhost:8000/ws/events?token=abc",
        onMessage,
      }),
    );

    expect(MockWebSocket.instances).toHaveLength(1);

    act(() => {
      MockWebSocket.instances[0].simulateClose();
    });

    // 1回目の再接続は1秒後
    act(() => {
      vi.advanceTimersByTime(999);
    });
    expect(MockWebSocket.instances).toHaveLength(1);
    act(() => {
      vi.advanceTimersByTime(1);
    });
    expect(MockWebSocket.instances).toHaveLength(2);

    act(() => {
      MockWebSocket.instances[1].simulateClose();
    });

    // 2回目の再接続は2秒後
    act(() => {
      vi.advanceTimersByTime(1999);
    });
    expect(MockWebSocket.instances).toHaveLength(2);
    act(() => {
      vi.advanceTimersByTime(1);
    });
    expect(MockWebSocket.instances).toHaveLength(3);
  });

  it("再接続間隔は上限30秒でキャップされる", () => {
    const onMessage = vi.fn();
    renderHook(() =>
      useWebSocket({
        url: "ws://localhost:8000/ws/events?token=abc",
        onMessage,
      }),
    );

    // 連続して切断させ、間隔が1,2,4,8,16,30,30...と増えることを確認する
    const expectedDelays = [1000, 2000, 4000, 8000, 16000, 30000, 30000];
    for (const delay of expectedDelays) {
      const countBefore = MockWebSocket.instances.length;
      act(() => {
        MockWebSocket.instances[countBefore - 1].simulateClose();
      });
      act(() => {
        vi.advanceTimersByTime(delay - 1);
      });
      expect(MockWebSocket.instances).toHaveLength(countBefore);
      act(() => {
        vi.advanceTimersByTime(1);
      });
      expect(MockWebSocket.instances).toHaveLength(countBefore + 1);
    }
  });

  it("正常接続後は再接続間隔がリセットされる", () => {
    const onMessage = vi.fn();
    renderHook(() =>
      useWebSocket({
        url: "ws://localhost:8000/ws/events?token=abc",
        onMessage,
      }),
    );

    act(() => {
      MockWebSocket.instances[0].simulateClose();
    });
    act(() => {
      vi.advanceTimersByTime(1000);
    });
    expect(MockWebSocket.instances).toHaveLength(2);

    // 再接続成功(open)後に切断すると、再び1秒からリトライする
    act(() => {
      MockWebSocket.instances[1].simulateOpen();
      MockWebSocket.instances[1].simulateClose();
    });
    act(() => {
      vi.advanceTimersByTime(999);
    });
    expect(MockWebSocket.instances).toHaveLength(2);
    act(() => {
      vi.advanceTimersByTime(1);
    });
    expect(MockWebSocket.instances).toHaveLength(3);
  });
});
