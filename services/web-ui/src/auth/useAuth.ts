import { useContext } from "react";
import { AuthContext, type AuthState } from "./AuthContext";

/** `AuthProvider`配下で認証状態・login/logoutを取得するフック。 */
export function useAuth(): AuthState {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuthはAuthProviderの内側で使用してください");
  }
  return context;
}
