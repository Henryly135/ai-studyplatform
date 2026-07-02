import { describe, expect, it } from "vitest";

import { isUsableAccessToken } from "./accessToken";

const NOW_MS = 1_800_000_000_000;

function base64UrlEncode(value: unknown) {
  const json = typeof value === "string" ? value : JSON.stringify(value);
  return btoa(json).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/u, "");
}

function makeToken(payload: unknown) {
  return `${base64UrlEncode({ alg: "HS256", typ: "JWT" })}.${base64UrlEncode(payload)}.signature`;
}

describe("access token usability", () => {
  it("accepts a well-formed unexpired JWT access token", () => {
    expect(isUsableAccessToken(makeToken({ exp: NOW_MS / 1000 + 60 }), NOW_MS)).toBe(true);
  });

  it("handles base64url payloads that require padding", () => {
    const payload = base64UrlEncode({ exp: NOW_MS / 1000 + 60, sub: "a" });
    expect(payload.length % 4).not.toBe(0);
    expect(isUsableAccessToken(`header.${payload}.signature`, NOW_MS)).toBe(true);
  });

  it.each([
    ["missing token", null],
    ["empty token", ""],
    ["single segment token", "not-a-jwt"],
    ["missing signature", "header.payload."],
    ["invalid payload json", `header.${base64UrlEncode("not-json")}.signature`],
    ["missing exp", makeToken({ sub: "1" })],
    ["non-numeric exp", makeToken({ exp: "1800000001" })],
    ["expired token", makeToken({ exp: NOW_MS / 1000 - 1 })],
  ])("rejects %s", (_label, token) => {
    expect(isUsableAccessToken(token, NOW_MS)).toBe(false);
  });
});
