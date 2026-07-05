import type { Role } from "./AuthContext";

export interface JwtPayload {
  sub?: string;
  role?: Role;
  exp?: number;
}

/** JWTのpayload部分をデコードする(署名検証は行わない。UI表示制御用途)。 */
export function decodeJwtPayload(token: string): JwtPayload | null {
  try {
    const parts = token.split(".");
    if (parts.length < 2) {
      return null;
    }
    const base64 = parts[1].replace(/-/g, "+").replace(/_/g, "/");
    const padded = base64 + "=".repeat((4 - (base64.length % 4)) % 4);
    const json = atob(padded);
    return JSON.parse(json) as JwtPayload;
  } catch {
    return null;
  }
}

/** トークンからロールを取得する。不明・未認証時は`null`。 */
export function getRoleFromToken(token: string | null): Role | null {
  if (!token) {
    return null;
  }
  const role = decodeJwtPayload(token)?.role;
  if (role === "admin" || role === "editor" || role === "viewer") {
    return role;
  }
  return null;
}
