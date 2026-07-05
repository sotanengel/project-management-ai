import type { paths } from "./schema";

/** APIサーバーのベースURL。`.env`の`VITE_API_BASE_URL`で上書き可能。 */
export const API_BASE_URL: string =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ??
  "http://localhost:8000";

/** WebSocketエンドポイントのベースURL(`http(s)`→`ws(s)`に変換)。 */
export function resolveWebSocketUrl(token: string): string {
  const wsBase = API_BASE_URL.replace(/^http/, "ws");
  return `${wsBase}/ws/events?token=${encodeURIComponent(token)}`;
}

/** 現在保持しているJWT(メモリ上)を返す関数。AuthContextから注入される。 */
let tokenGetter: () => string | null = () => null;

/** APIクライアントが参照するトークン取得関数を設定する(AuthProviderが呼ぶ)。 */
export function setTokenGetter(getter: () => string | null): void {
  tokenGetter = getter;
}

export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(status: number, detail: unknown) {
    super(typeof detail === "string" ? detail : `APIエラー(status=${status})`);
    this.status = status;
    this.detail = detail;
  }
}

type JsonBody = Record<string, unknown> | unknown[] | undefined;

interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "DELETE";
  body?: JsonBody;
  query?: Record<string, string | number | boolean | undefined>;
  /** trueの場合、Authorizationヘッダを付与しない(ログイン等)。 */
  skipAuth?: boolean;
}

function buildUrl(path: string, query?: RequestOptions["query"]): string {
  const url = new URL(path.replace(/^\//, ""), `${API_BASE_URL}/`);
  if (query) {
    for (const [key, value] of Object.entries(query)) {
      if (value !== undefined) {
        url.searchParams.set(key, String(value));
      }
    }
  }
  return url.toString();
}

/** fetchラッパー: JWTのAuthorizationヘッダ付与・エラーの共通ハンドリングを行う。 */
export async function apiRequest<TResponse>(
  path: string,
  options: RequestOptions = {},
): Promise<TResponse> {
  const { method = "GET", body, query, skipAuth } = options;
  const headers: Record<string, string> = {};
  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
  }
  if (!skipAuth) {
    const token = tokenGetter();
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }
  }

  const response = await fetch(buildUrl(path, query), {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (!response.ok) {
    let detail: unknown;
    try {
      const data = await response.json();
      detail = data?.detail ?? data;
    } catch {
      detail = response.statusText;
    }
    throw new ApiError(response.status, detail);
  }

  if (response.status === 204) {
    return undefined as TResponse;
  }

  return (await response.json()) as TResponse;
}

// --- 型の再エクスポート(schema.d.tsの型をアプリ全体で使いやすくする) ---
export type LoginRequest =
  paths["/auth/login"]["post"]["requestBody"]["content"]["application/json"];
export type TokenResponse =
  paths["/auth/login"]["post"]["responses"][200]["content"]["application/json"];
export type ProposalResponse =
  paths["/approvals"]["get"]["responses"][200]["content"]["application/json"][number];
export type DecideRequest =
  paths["/approvals/{proposal_id}/decide"]["post"]["requestBody"]["content"]["application/json"];

// --- 認証API ---
export function login(request: LoginRequest): Promise<TokenResponse> {
  return apiRequest<TokenResponse>("/auth/login", {
    method: "POST",
    body: request,
    skipAuth: true,
  });
}

export function refresh(accessToken: string): Promise<TokenResponse> {
  return apiRequest<TokenResponse>("/auth/refresh", {
    method: "POST",
    body: { access_token: accessToken },
    skipAuth: true,
  });
}

// --- 承認API ---
export function listApprovals(status?: string): Promise<ProposalResponse[]> {
  return apiRequest<ProposalResponse[]>("/approvals", { query: { status } });
}

export function decideApproval(
  proposalId: string,
  request: DecideRequest,
): Promise<ProposalResponse> {
  return apiRequest<ProposalResponse>(`/approvals/${proposalId}/decide`, {
    method: "POST",
    body: request,
  });
}

// --- PMDF汎用API ---
export function listPmdfEntities<T = Record<string, unknown>>(
  kind: string,
  params?: { product?: string; limit?: number; offset?: number },
): Promise<T[]> {
  return apiRequest<T[]>(`/pmdf/${kind}`, { query: params });
}

export function getPmdfEntity<T = Record<string, unknown>>(
  kind: string,
  id: string,
): Promise<T> {
  return apiRequest<T>(`/pmdf/${kind}/${id}`);
}
