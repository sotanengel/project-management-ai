import {
  createContext,
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import * as api from "../api/client";
import { setTokenGetter } from "../api/client";

export type Role = "admin" | "editor" | "viewer";

export interface AuthState {
  token: string | null;
  isAuthenticated: boolean;
  login: (request: api.LoginRequest) => Promise<void>;
  logout: () => void;
}

export const AuthContext = createContext<AuthState | null>(null);

/**
 * JWTをメモリ(Reactステート)にのみ保持する認証コンテキスト。
 *
 * localStorage等の永続化は行わない(ページリロードで再ログインが必要になる
 * シンプルな戦略。XSS時のトークン窃取面を減らすためのトレードオフ)。
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(null);

  useEffect(() => {
    setTokenGetter(() => token);
  }, [token]);

  const login = useCallback(async (request: api.LoginRequest) => {
    const response = await api.login(request);
    setToken(response.access_token);
  }, []);

  const logout = useCallback(() => {
    setToken(null);
  }, []);

  const value = useMemo<AuthState>(
    () => ({
      token,
      isAuthenticated: token !== null,
      login,
      logout,
    }),
    [token, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
