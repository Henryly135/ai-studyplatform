import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { initializeGlobalProfile } from "./profile";

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

const profilePayload = {
  supportRole: "coach",
  helpStyle: "guided",
  learningFocus: "practice",
  responseTone: "warm",
};

describe("profile service normalization", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(NOW_MS));
    vi.stubGlobal("localStorage", createMemoryStorage());
    vi.stubGlobal("window", {
      location: {
        pathname: "/home/ai/profile-init",
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

  it("normalizes malformed global profile responses to display-safe values", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        mockJsonResponse({
          learner_id: "-4",
          profile_type: 123,
          version: "bad-version",
          object_key: 456,
          content: 789,
          is_default_profile: "false",
          created_at: null,
          updated_at: "2026-07-02T00:00:00Z",
        })
      )
    );

    const result = await initializeGlobalProfile(profilePayload);

    expect(result).toEqual({
      learnerId: 0,
      profileType: "123",
      version: null,
      objectKey: "456",
      content: "789",
      isDefaultProfile: false,
      createdAt: null,
      updatedAt: "2026-07-02T00:00:00Z",
    });
  });

  it("keeps user-readable error messages from failed profile initialization", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(mockJsonResponse({ error: { message: "Profile provider unavailable" } }, 503))
    );

    await expect(initializeGlobalProfile(profilePayload)).rejects.toThrow("Profile provider unavailable");
  });
});
