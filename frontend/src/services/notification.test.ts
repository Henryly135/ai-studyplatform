import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getNotificationUnreadCount, listMyNotifications, listNotifications } from "./notification";

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

describe("notification service normalization", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(NOW_MS));
    vi.stubGlobal("localStorage", createMemoryStorage());
    vi.stubGlobal("window", {
      location: {
        pathname: "/home/notifications",
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

  it("normalizes malformed recipient notification pagination and counters", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        mockJsonResponse({
          items: [
            {
              notificationId: "not-a-number",
              notificationUuid: "notification_1",
              actorUserId: -4,
              actorUserUuid: "actor_1",
              notificationType: "course",
              title: "New module",
              body: "Start here",
              metadataJson: "bad-metadata",
              recipientUserId: "bad-recipient",
              recipientUserUuid: "learner_1",
              recipientEmail: "learner@example.test",
              recipientName: "Learner",
              isRead: "false",
              isHidden: "true",
              receivedAt: "2026-07-02T00:00:00Z",
            },
          ],
          page: "bad-page",
          pageSize: "0",
          total: "no-total",
          totalPages: -5,
        })
      )
    );

    const result = await listMyNotifications("token");

    expect(result.page).toBe(1);
    expect(result.pageSize).toBe(1);
    expect(result.total).toBe(1);
    expect(result.totalPages).toBe(1);
    expect(result.items[0].notificationId).toBe(0);
    expect(result.items[0].actorUserId).toBeNull();
    expect(result.items[0].metadataJson).toBeNull();
    expect(result.items[0].recipientUserId).toBe(0);
    expect(result.items[0].isRead).toBe(false);
    expect(result.items[0].isHidden).toBe(true);
  });

  it("normalizes malformed admin notification pagination to finite values", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        mockJsonResponse({
          items: [],
          page: "2",
          pageSize: "not-size",
          total: -9,
          totalPages: "bad-pages",
        })
      )
    );

    const result = await listNotifications("token");

    expect(result.page).toBe(2);
    expect(result.pageSize).toBe(20);
    expect(result.total).toBe(0);
    expect(result.totalPages).toBe(1);
  });

  it("normalizes malformed unread counts to a non-negative number", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        mockJsonResponse({
          recipientUserId: "7",
          recipientUserUuid: "learner_1",
          unreadCount: "not-a-count",
        })
      )
    );

    const result = await getNotificationUnreadCount("token");

    expect(result.recipientUserId).toBe(7);
    expect(result.unreadCount).toBe(0);
  });
});
