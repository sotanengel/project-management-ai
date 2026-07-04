import { createContext, useMemo, useState, type ReactNode } from "react";
import { useAuth } from "../auth/useAuth";
import { resolveWebSocketUrl } from "../api/client";
import { useWebSocket, type WsEvent } from "../hooks/useWebSocket";

/** `agent.activity`イベント(E5-9チャットタスクの状態遷移通知)のペイロード。 */
export interface AgentActivityEvent {
  task_id: string;
  status: "pending" | "running" | "done" | "failed";
  product_id?: string | null;
  intent?: string | null;
}

/** 直近活動として画面に保持する最大件数。 */
const MAX_RECENT_ACTIVITY = 200;

export interface AppState {
  pendingApprovalCount: number;
  isWsConnected: boolean;
  /** `agent.activity`イベントを新しい順に蓄積したもの(直近{@link MAX_RECENT_ACTIVITY}件まで)。 */
  recentActivity: AgentActivityEvent[];
}

export const AppStateContext = createContext<AppState | null>(null);

/**
 * WebSocket接続・承認待ち件数・直近のエージェント活動などアプリ全体で
 * 共有するグローバル状態。
 *
 * `AuthProvider`配下に置くこと。未認証(token無し)の間はWebSocket接続を
 * 試みない(E7-2受け入れ条件)。
 */
export function AppStateProvider({ children }: { children: ReactNode }) {
  const { token } = useAuth();
  const [pendingApprovalCount, setPendingApprovalCount] = useState(0);
  const [isWsConnected, setIsWsConnected] = useState(false);
  const [recentActivity, setRecentActivity] = useState<AgentActivityEvent[]>(
    [],
  );

  const wsUrl = token ? resolveWebSocketUrl(token) : null;

  useWebSocket({
    url: wsUrl,
    onOpen: () => setIsWsConnected(true),
    onClose: () => setIsWsConnected(false),
    onMessage: (event: WsEvent) => {
      if (event.type === "approval.count_changed") {
        const data = event.data as { count?: number };
        if (typeof data.count === "number") {
          setPendingApprovalCount(data.count);
        }
      } else if (event.type === "agent.activity") {
        const data = event.data as AgentActivityEvent;
        setRecentActivity((prev) =>
          [data, ...prev].slice(0, MAX_RECENT_ACTIVITY),
        );
      }
    },
  });

  const value = useMemo<AppState>(
    () => ({ pendingApprovalCount, isWsConnected, recentActivity }),
    [pendingApprovalCount, isWsConnected, recentActivity],
  );

  return (
    <AppStateContext.Provider value={value}>
      {children}
    </AppStateContext.Provider>
  );
}
