import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { listCourseForumPosts, listForumComments } from "./forum";

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

describe("forum service normalization", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(NOW_MS));
    vi.stubGlobal("localStorage", createMemoryStorage());
    vi.stubGlobal("window", {
      location: {
        pathname: "/home",
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

  it("normalizes malformed forum post counts and pagination to finite values", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      mockJsonResponse({
        items: [
          {
            postId: "not-a-number",
            postUuid: "post_1",
            courseId: "42",
            courseUuid: "course_1",
            authorUserId: "bad-user-id",
            authorUserUuid: "user_1",
            authorName: "Learner",
            content: "Question",
            commentCount: "many",
            previewComments: [
              {
                commentId: "abc",
                commentUuid: "comment_1",
                postId: "1",
                postUuid: "post_1",
                courseId: "42",
                courseUuid: "course_1",
                authorUserId: "7",
                authorUserUuid: "user_2",
                authorName: "Educator",
                content: "Answer",
                rootCommentId: -3,
                replyToCommentId: "8",
                replyCount: "none",
              },
            ],
          },
        ],
        page: "bad-page",
        pageSize: "0",
        total: "not-total",
        totalPages: -4,
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    const result = await listCourseForumPosts("course_1");

    expect(result.page).toBe(1);
    expect(result.pageSize).toBe(1);
    expect(result.total).toBe(1);
    expect(result.totalPages).toBe(1);
    expect(result.items[0].postId).toBe(0);
    expect(result.items[0].courseId).toBe(42);
    expect(result.items[0].authorUserId).toBe(0);
    expect(result.items[0].commentCount).toBe(0);
    expect(result.items[0].previewComments[0].commentId).toBe(0);
    expect(result.items[0].previewComments[0].rootCommentId).toBeNull();
    expect(result.items[0].previewComments[0].replyToCommentId).toBe(8);
    expect(result.items[0].previewComments[0].replyCount).toBe(0);
  });

  it("normalizes malformed forum comment pagination to finite values", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        mockJsonResponse({
          items: [],
          page: "2",
          pageSize: "not-size",
          total: -8,
          totalPages: "invalid",
        })
      )
    );

    const result = await listForumComments("post_1");

    expect(result.page).toBe(2);
    expect(result.pageSize).toBe(20);
    expect(result.total).toBe(0);
    expect(result.totalPages).toBe(1);
  });
});
