import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  getCurrentUser,
  getCurrentUserPermissions,
  loginUser,
  registerUser,
  switchCurrentRole,
  validateEducatorInviteToken,
} from "./auth";

const NOW_MS = 1_800_000_000_000;

function base64UrlEncode(value: unknown) {
  return btoa(JSON.stringify(value)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/u, "");
}

function makeToken(exp: number) {
  return `${base64UrlEncode({ alg: "HS256", typ: "JWT" })}.${base64UrlEncode({ exp })}.signature`;
}

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

function mockJsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("auth service normalization", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(NOW_MS));
    vi.stubGlobal("localStorage", createMemoryStorage());
    vi.stubGlobal("window", {
      location: {
        pathname: "/login",
        assign: vi.fn(),
      },
    });
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("normalizes login payloads and rejects unusable access tokens before storage", async () => {
    const validToken = makeToken(NOW_MS / 1000 + 60);
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        mockJsonResponse({
          access_token: validToken,
          token_type: "Bearer",
          expires_in: "-10",
          should_show_global_profile_init_prompt: "true",
          user: {
            id: "5",
            user_uuid: "user-5",
            email: "learner@example.com",
            user_name: "Learner",
            identity: "Learner",
            available_identities: ["Learner", "Educator", "Admin"],
            email_verified: "true",
            account_status: "active",
          },
        })
      )
      .mockResolvedValueOnce(
        mockJsonResponse({
          accessToken: "not-a-jwt",
          tokenType: "bearer",
          expiresIn: 3600,
          user: {
            id: 5,
            userUuid: "user-5",
            email: "learner@example.com",
            userName: "Learner",
            identity: "Learner",
            emailVerified: true,
          },
        })
      );
    vi.stubGlobal("fetch", fetchMock);

    const login = await loginUser({ email: "learner@example.com", password: "Password1!" });

    expect(login.accessToken).toBe(validToken);
    expect(login.tokenType).toBe("bearer");
    expect(login.expiresIn).toBe(0);
    expect(login.shouldShowGlobalProfileInitPrompt).toBe(true);
    expect(login.user.id).toBe(5);
    expect(login.user.availableIdentities).toEqual(["Learner", "Educator", "Admin"]);
    expect(login.user.emailVerified).toBe(true);
    await expect(loginUser({ email: "learner@example.com", password: "Password1!" })).rejects.toThrow(
      "登录响应无效"
    );
  });

  it("normalizes current user, registration, and permissions responses", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        mockJsonResponse({
          detail: 123,
          user: {
            id: "6",
            user_uuid: "user-6",
            email: "educator@example.com",
            user_name: "Educator",
            identity: "Educator",
            email_verified: "false",
          },
        })
      )
      .mockResolvedValueOnce(
        mockJsonResponse({
          id: "-1",
          user_uuid: "user-1",
          email: "bad@example.com",
          user_name: "Bad Identity",
          identity: "Owner",
          email_verified: "yes",
          account_status: null,
        })
      )
      .mockResolvedValueOnce(
        mockJsonResponse({
          permissions: [
            {
              permission_id: "7",
              permission_code: "course:create",
              permission_name: "Create course",
              description: null,
            },
            {
              permissionId: -1,
              permissionCode: 123,
              permissionName: "Bad permission",
              description: 456,
            },
          ],
        })
      );
    vi.stubGlobal("fetch", fetchMock);
    localStorage.setItem("accessToken", makeToken(NOW_MS / 1000 + 60));

    const register = await registerUser({
      userName: "Educator",
      email: "educator@example.com",
      password: "Password1!",
      identity: "Educator",
    });
    const currentUser = await getCurrentUser("");
    const permissions = await getCurrentUserPermissions("");

    expect(register.detail).toBe("123");
    expect(register.user?.id).toBe(6);
    expect(register.user?.emailVerified).toBe(false);
    expect(currentUser.id).toBe(0);
    expect(currentUser.identity).toBe("Learner");
    expect(currentUser.availableIdentities).toEqual(["Learner"]);
    expect(currentUser.emailVerified).toBe(true);
    expect(currentUser.accountStatus).toBeUndefined();
    expect(permissions.permissions[0].permissionId).toBe(7);
    expect(permissions.permissions[1].permissionId).toBe(0);
    expect(permissions.permissions[1].permissionCode).toBe("123");
    expect(permissions.permissions[1].description).toBe("456");
  });

  it("switches the active role with the stored bearer token", async () => {
    const currentToken = makeToken(NOW_MS / 1000 + 60);
    const switchedToken = makeToken(NOW_MS / 1000 + 120);
    localStorage.setItem("accessToken", currentToken);
    const fetchMock = vi.fn().mockResolvedValue(
      mockJsonResponse({
        accessToken: switchedToken,
        tokenType: "bearer",
        expiresIn: 3600,
        user: {
          id: 7,
          userUuid: "user-7",
          email: "demo@example.com",
          userName: "Local Demo",
          identity: "Admin",
          availableIdentities: ["Learner", "Educator", "Admin"],
          emailVerified: true,
          accountStatus: "active",
        },
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    const result = await switchCurrentRole("Admin");

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/auth/switch-role",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({ Authorization: `Bearer ${currentToken}` }),
        body: JSON.stringify({ identity: "Admin" }),
      })
    );
    expect(result.accessToken).toBe(switchedToken);
    expect(result.user.identity).toBe("Admin");
  });

  it("rejects invite validation payloads that are not explicitly valid", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        mockJsonResponse({
          valid: "true",
          expires_at: "2026-07-03T00:00:00Z",
        })
      )
      .mockResolvedValueOnce(
        mockJsonResponse({
          valid: "false",
          expires_at: "2026-07-03T00:00:00Z",
        })
      );
    vi.stubGlobal("fetch", fetchMock);

    await expect(validateEducatorInviteToken("valid-token")).resolves.toEqual({
      valid: true,
      expiresAt: "2026-07-03T00:00:00Z",
    });
    await expect(validateEducatorInviteToken("invalid-token")).rejects.toThrow(
      "Invalid or expired invite link."
    );
  });
});
