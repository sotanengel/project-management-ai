import { describe, expect, it } from "vitest";
import { decodeJwtPayload, getRoleFromToken } from "./jwt";

function makeToken(payload: Record<string, unknown>): string {
  const header = btoa(JSON.stringify({ alg: "HS256", typ: "JWT" }))
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");
  const body = btoa(JSON.stringify(payload))
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");
  return `${header}.${body}.signature`;
}

describe("jwt", () => {
  it("decodeJwtPayloadがroleを返す", () => {
    const token = makeToken({ sub: "user-1", role: "admin" });
    expect(decodeJwtPayload(token)).toEqual({
      sub: "user-1",
      role: "admin",
    });
  });

  it("getRoleFromTokenが有効なロールを返す", () => {
    const token = makeToken({ role: "editor" });
    expect(getRoleFromToken(token)).toBe("editor");
  });

  it("不正なトークンはnullを返す", () => {
    expect(getRoleFromToken("not-a-jwt")).toBeNull();
    expect(getRoleFromToken(null)).toBeNull();
  });
});
