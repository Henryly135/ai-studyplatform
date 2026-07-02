import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  checkAdminAiProviderCredentialHealth,
  deleteAdminAiProviderCredential,
  generateEducatorInviteToken,
  getAdminUsers,
  getPendingEducatorApprovals,
  listAdminAiProviderCredentials,
  listEducatorInviteTokens,
  saveAdminAiProviderCredential,
  sendEducatorInviteEmail,
  setAdminAiDefaultModel,
} from "./admin";

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

describe("admin service normalization", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(NOW_MS));
    vi.stubGlobal("localStorage", createMemoryStorage());
    vi.stubGlobal("window", {
      location: {
        pathname: "/home/user-management",
        assign: vi.fn(),
      },
    });
    localStorage.setItem("accessToken", makeToken(NOW_MS / 1000 + 60));
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("normalizes malformed user and educator approval list responses", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        mockJsonResponse({
          users: [
            {
              id: "7",
              user_uuid: "user-7",
              email: "admin@example.com",
              user_name: "Admin User",
              identity: "Unknown",
              role_codes: ["admin", 5],
              email_verified: "false",
              account_status: "active",
              created_at: "2026-07-02T00:00:00Z",
              updated_at: "2026-07-02T00:01:00Z",
              last_login_at: null,
            },
            null,
          ],
        })
      )
      .mockResolvedValueOnce(
        mockJsonResponse({
          requests: [
            {
              request_uuid: "request-1",
              request_status: "approved",
              submitted_at: "2026-07-01T00:00:00Z",
              updated_at: "2026-07-02T00:00:00Z",
              reviewed_at: null,
              review_comment: 123,
              supporting_info: null,
              supporting_file_url: 456,
              user_id: "11",
              user_uuid: "user-11",
              email: "teacher@example.com",
              user_name: "Teacher",
              identity: "Educator",
              account_status: "active",
              email_verified: "true",
              reviewer_user_id: -1,
              reviewer_user_uuid: null,
              reviewer_email: "reviewer@example.com",
              reviewer_name: null,
            },
            "bad-row",
          ],
        })
      );
    vi.stubGlobal("fetch", fetchMock);

    const users = await getAdminUsers("");
    const approvals = await getPendingEducatorApprovals("");

    expect(users.users).toHaveLength(1);
    expect(users.users[0].id).toBe(7);
    expect(users.users[0].identity).toBe("Learner");
    expect(users.users[0].roleCodes).toEqual(["admin", "5"]);
    expect(users.users[0].emailVerified).toBe(false);
    expect(users.users[0].lastLoginAt).toBeNull();
    expect(approvals.requests).toHaveLength(1);
    expect(approvals.requests[0].requestStatus).toBe("approved");
    expect(approvals.requests[0].reviewComment).toBe("123");
    expect(approvals.requests[0].supportingFileUrl).toBe("456");
    expect(approvals.requests[0].emailVerified).toBe(true);
    expect(approvals.requests[0].reviewerUserId).toBeNull();
  });

  it("normalizes invite token and invite email delivery responses", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        mockJsonResponse({
          invite_uuid: "invite-1",
          raw_token: "raw-token",
          expires_at: "2026-07-03T00:00:00Z",
          invite_url: "https://app.example/register/educator-invite?token=raw-token",
        })
      )
      .mockResolvedValueOnce(
        mockJsonResponse({
          tokens: [
            {
              invite_uuid: "invite-1",
              created_at: "2026-07-02T00:00:00Z",
              expires_at: "2026-07-03T00:00:00Z",
              used_at: null,
              is_used: "false",
            },
            {
              inviteUuid: "invite-2",
              createdAt: "2026-07-02T01:00:00Z",
              expiresAt: "2026-07-03T01:00:00Z",
              usedAt: "2026-07-02T02:00:00Z",
              isUsed: "yes",
            },
          ],
        })
      )
      .mockResolvedValueOnce(
        mockJsonResponse({
          detail: 123,
          email_delivery: {
            attempted: "true",
            delivered: "false",
            reason: 456,
          },
        })
      );
    vi.stubGlobal("fetch", fetchMock);

    const generated = await generateEducatorInviteToken("");
    const tokens = await listEducatorInviteTokens("");
    const email = await sendEducatorInviteEmail("", generated.inviteUuid, {
      recipientEmail: "teacher@example.com",
      inviteUrl: generated.inviteUrl,
    });

    expect(generated.inviteUuid).toBe("invite-1");
    expect(generated.rawToken).toBe("raw-token");
    expect(generated.inviteUrl).toContain("raw-token");
    expect(tokens.tokens[0].isUsed).toBe(false);
    expect(tokens.tokens[1].isUsed).toBe(true);
    expect(email.detail).toBe("123");
    expect(email.emailDelivery.attempted).toBe(true);
    expect(email.emailDelivery.delivered).toBe(false);
    expect(email.emailDelivery.reason).toBe("456");
  });

  it("manages AI provider credentials and default model settings", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        mockJsonResponse({
          providers: [
            {
              provider: "deepseek",
              providerLabel: "DeepSeek",
              backendSupported: true,
              configured: "true",
              apiKeyHint: "****1234",
              healthStatus: "ready",
              lastCheckedAt: null,
              updated_at: "2026-07-02T00:00:00Z",
            },
          ],
        })
      )
      .mockResolvedValueOnce(
        mockJsonResponse({
          provider: "deepseek",
          configured: true,
          apiKeyHint: "****5678",
          healthStatus: "ready",
        })
      )
      .mockResolvedValueOnce(mockJsonResponse({ detail: "deleted" }))
      .mockResolvedValueOnce(
        mockJsonResponse({
          provider: "deepseek",
          ok: "true",
          status: "ready",
          checked_at: "2026-07-02T01:00:00Z",
          message: 123,
        })
      )
      .mockResolvedValueOnce(
        mockJsonResponse({
          defaultChatModelId: "deepseek:deepseek-v4-flash",
        })
      );
    vi.stubGlobal("fetch", fetchMock);

    const credentials = await listAdminAiProviderCredentials("");
    const saved = await saveAdminAiProviderCredential("", {
      provider: "deepseek",
      apiKey: "test-key",
      defaultModelId: "deepseek:deepseek-v4-flash",
    });
    await deleteAdminAiProviderCredential("", "deepseek");
    const health = await checkAdminAiProviderCredentialHealth("", "deepseek");
    const defaultModel = await setAdminAiDefaultModel("", { modelId: "deepseek:deepseek-v4-flash" });

    expect(credentials.credentials[0].configured).toBe(true);
    expect(credentials.credentials[0].backendSupported).toBe(true);
    expect(credentials.credentials[0].keyPreview).toBe("****1234");
    expect(saved.keyPreview).toBe("****5678");
    expect(health.ok).toBe(true);
    expect(health.message).toBe("123");
    expect(defaultModel.modelId).toBe("deepseek:deepseek-v4-flash");
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "/api/ai/admin/ai/providers/deepseek/credential",
      expect.objectContaining({
        method: "PUT",
        body: JSON.stringify({
          apiKey: "test-key",
          baseUrl: null,
          enabled: true,
        }),
      })
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      5,
      "/api/ai/admin/ai/defaults",
      expect.objectContaining({
        method: "PATCH",
        body: JSON.stringify({ defaultChatModelId: "deepseek:deepseek-v4-flash" }),
      })
    );
  });
});
