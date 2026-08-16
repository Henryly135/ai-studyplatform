import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  buildAuthHeaders,
  clearStoredSession,
  getStoredAccessToken,
  getStoredCurrentUser,
  isAuthenticationFailure,
} from "./api";

const NOW_MS = 1_800_000_000_000;
let locationAssign: ReturnType<typeof vi.fn>;

function createMemoryStorage(): Storage {
  const values = new Map<string, string>();

  return {
    get length() {
      return values.size;
    },
    clear() {
      values.clear();
    },
    getItem(key: string) {
      return values.get(key) ?? null;
    },
    key(index: number) {
      return Array.from(values.keys())[index] ?? null;
    },
    removeItem(key: string) {
      values.delete(key);
    },
    setItem(key: string, value: string) {
      values.set(key, String(value));
    },
  };
}

function base64UrlEncode(value: unknown) {
  return btoa(JSON.stringify(value)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/u, "");
}

function makeToken(exp: number) {
  return `${base64UrlEncode({ alg: "HS256", typ: "JWT" })}.${base64UrlEncode({ exp })}.signature`;
}

describe("shared API authentication helpers", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(NOW_MS));
    locationAssign = vi.fn();
    vi.stubGlobal("localStorage", createMemoryStorage());
    vi.stubGlobal("window", {
      location: {
        pathname: "/home",
        assign: locationAssign,
      },
    });
    localStorage.clear();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("returns the stored token when it is a usable JWT", () => {
    const token = makeToken(NOW_MS / 1000 + 60);
    localStorage.setItem("accessToken", token);
    localStorage.setItem("tokenType", "bearer");
    localStorage.setItem("currentUser", JSON.stringify({ userUuid: "user_1" }));

    expect(getStoredAccessToken()).toBe(token);
  });

  it.each([
    ["missing token", null],
    ["malformed token", "not-a-jwt"],
    ["expired token", makeToken(NOW_MS / 1000 - 60)],
  ])("clears session and blocks auth headers for %s", (_label, token) => {
    if (token) {
      localStorage.setItem("accessToken", token);
    }
    localStorage.setItem("tokenType", "bearer");
    localStorage.setItem("currentUser", JSON.stringify({ userUuid: "user_1" }));

    expect(() => getStoredAccessToken()).toThrow("Invalid credentials");
    expect(localStorage.getItem("accessToken")).toBeNull();
    expect(localStorage.getItem("tokenType")).toBeNull();
    expect(localStorage.getItem("currentUser")).toBeNull();
    expect(locationAssign).toHaveBeenCalledWith("/login");
  });

  it("builds authorization headers only after token usability is verified", () => {
    const token = makeToken(NOW_MS / 1000 + 60);
    localStorage.setItem("accessToken", token);

    expect(buildAuthHeaders({ "Content-Type": "application/json" })).toEqual({
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    });
  });

  it("clears all stored session values", () => {
    localStorage.setItem("accessToken", makeToken(NOW_MS / 1000 + 60));
    localStorage.setItem("tokenType", "bearer");
    localStorage.setItem("currentUser", JSON.stringify({ userUuid: "user_1" }));

    clearStoredSession();

    expect(localStorage.getItem("accessToken")).toBeNull();
    expect(localStorage.getItem("tokenType")).toBeNull();
    expect(localStorage.getItem("currentUser")).toBeNull();
  });

  it("normalizes the stored current user cache without trusting malformed fields", () => {
    localStorage.setItem(
      "currentUser",
      JSON.stringify({
        id: "7",
        user_uuid: "user_7",
        email: "educator@example.com",
        user_name: "Educator",
        identity: "Educator",
        available_identities: ["Educator", "Admin", "Educator", "Owner"],
        email_verified: "false",
        account_status: 123,
      })
    );

    expect(getStoredCurrentUser()).toEqual({
      id: 7,
      userUuid: "user_7",
      email: "educator@example.com",
      userName: "Educator",
      identity: "Educator",
      availableIdentities: ["Educator", "Admin"],
      emailVerified: false,
      accountStatus: "123",
    });
    expect(localStorage.getItem("currentUser")).not.toBeNull();
  });

  it.each([
    ["malformed JSON", "not-json"],
    ["unsupported identity", JSON.stringify({ identity: "Owner" })],
    ["non-object payload", JSON.stringify(["Learner"])],
  ])("removes invalid stored current user cache for %s", (_label, value) => {
    localStorage.setItem("currentUser", value);

    expect(getStoredCurrentUser()).toBeNull();
    expect(localStorage.getItem("currentUser")).toBeNull();
    expect(locationAssign).not.toHaveBeenCalled();
  });

  it("detects authentication failures across status, detail, and error payload shapes", () => {
    expect(isAuthenticationFailure(401, null)).toBe(true);
    expect(isAuthenticationFailure(400, { detail: "Invalid credentials" })).toBe(true);
    expect(isAuthenticationFailure(403, { detail: { code: "UNAUTHORIZED" } })).toBe(true);
    expect(isAuthenticationFailure(403, { error: { message: "Unable to resolve current user" } })).toBe(true);
    expect(isAuthenticationFailure(403, { error: { message: "无法解析当前用户" } })).toBe(true);
    expect(isAuthenticationFailure(403, { detail: "COURSE_ENROLLMENT_REQUIRED" })).toBe(false);
  });
});
