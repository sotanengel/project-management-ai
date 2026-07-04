import { http, HttpResponse } from "msw";
import { API_BASE_URL } from "../api/client";

/** テスト用の正しい資格情報。 */
export const VALID_EMAIL = "pm@example.com";
export const VALID_PASSWORD = "correct-horse-battery-staple";
export const VALID_TOKEN = "test.jwt.token";

export const handlers = [
  http.post(`${API_BASE_URL}/auth/login`, async ({ request }) => {
    const body = (await request.json()) as {
      email: string;
      password: string;
      totp_code?: string | null;
    };
    if (body.email === VALID_EMAIL && body.password === VALID_PASSWORD) {
      return HttpResponse.json({
        access_token: VALID_TOKEN,
        token_type: "bearer",
      });
    }
    return HttpResponse.json({ detail: "認証に失敗しました" }, { status: 401 });
  }),

  http.get(`${API_BASE_URL}/approvals`, () => {
    return HttpResponse.json([]);
  }),

  http.get(`${API_BASE_URL}/pmdf/:kind`, () => {
    return HttpResponse.json([]);
  }),
];
