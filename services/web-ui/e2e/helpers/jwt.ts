/** E2E用の未署名JWT(ロール表示・Authorizationヘッダ送信用)。 */
export function makeTestToken(
  payload: Record<string, unknown> = { sub: "user:pm", role: "admin" },
): string {
  const header = btoa(JSON.stringify({ alg: "HS256", typ: "JWT" }))
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");
  const body = btoa(JSON.stringify(payload))
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");
  return `${header}.${body}.e2e-signature`;
}

export const ADMIN_TOKEN = makeTestToken({ sub: "user:pm", role: "admin" });
