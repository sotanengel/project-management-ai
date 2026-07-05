import { useContext } from "react";
import { AppStateContext, type AppState } from "./AppStateContext";

/** `AppStateProvider`配下でWebSocket接続状態・承認待ち件数を取得するフック。 */
export function useAppState(): AppState {
  const context = useContext(AppStateContext);
  if (!context) {
    throw new Error("useAppStateはAppStateProviderの内側で使用してください");
  }
  return context;
}
