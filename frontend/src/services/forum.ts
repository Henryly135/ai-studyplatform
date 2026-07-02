import type {
  CreateForumCommentPayload,
  CreateForumPostPayload,
  ForumComment,
  ForumPost,
  PaginatedForumCommentResponse,
  PaginatedForumPostResponse,
  UpdateForumCommentPayload,
  UpdateForumPostPayload,
} from "../types/forum";
import {
  buildAuthHeaders,
  handleAuthenticationFailureFromResponse,
  parseJsonText,
} from "./api";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "/api";
const COMMUNICATION_API_BASE_URL = API_BASE_URL.startsWith("/api")
  ? `${API_BASE_URL}/communication`
  : `${API_BASE_URL.replace(/\/$/, "")}/communication`;

function extractErrorMessage(payload: unknown, fallbackMessage: string) {
  if (payload && typeof payload === "object") {
    const detail = (payload as { detail?: unknown }).detail;
    if (typeof detail === "string" && detail.trim()) {
      return detail;
    }

    if (detail && typeof detail === "object") {
      const message = (detail as { message?: unknown }).message;
      if (typeof message === "string" && message.trim()) {
        return message;
      }
    }
  }

  return fallbackMessage;
}

function toFiniteNumber(value: unknown, fallback: number, minimum?: number) {
  const parsed =
    typeof value === "number"
      ? value
      : typeof value === "string" && value.trim()
        ? Number(value)
        : fallback;

  if (!Number.isFinite(parsed)) {
    return fallback;
  }

  return minimum === undefined ? parsed : Math.max(minimum, parsed);
}

function toNullableFiniteNumber(value: unknown) {
  if (value === null || value === undefined) {
    return null;
  }

  const parsed =
    typeof value === "number"
      ? value
      : typeof value === "string" && value.trim()
        ? Number(value)
        : Number.NaN;
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : null;
}

function normalizeForumComment(payload: Record<string, unknown>): ForumComment {
  return {
    commentId: toFiniteNumber(payload.commentId, 0, 0),
    commentUuid: String(payload.commentUuid ?? ""),
    postId: toFiniteNumber(payload.postId, 0, 0),
    postUuid: String(payload.postUuid ?? ""),
    courseId: toFiniteNumber(payload.courseId, 0, 0),
    courseUuid: String(payload.courseUuid ?? ""),
    authorUserId: toFiniteNumber(payload.authorUserId, 0, 0),
    authorUserUuid: String(payload.authorUserUuid ?? ""),
    authorEmail: String(payload.authorEmail ?? ""),
    authorName: String(payload.authorName ?? "Unknown author"),
    rootCommentId: toNullableFiniteNumber(payload.rootCommentId),
    rootCommentUuid: payload.rootCommentUuid == null ? null : String(payload.rootCommentUuid),
    replyToCommentId: toNullableFiniteNumber(payload.replyToCommentId),
    replyToCommentUuid:
      payload.replyToCommentUuid == null ? null : String(payload.replyToCommentUuid),
    replyToAuthorName: payload.replyToAuthorName == null ? null : String(payload.replyToAuthorName),
    content: String(payload.content ?? ""),
    commentKind: String(payload.commentKind ?? "user"),
    metadataJson:
      payload.metadataJson && typeof payload.metadataJson === "object"
        ? (payload.metadataJson as Record<string, unknown>)
        : null,
    isDeleted: Boolean(payload.isDeleted),
    deletedAt: payload.deletedAt == null ? null : String(payload.deletedAt),
    replyCount: toFiniteNumber(payload.replyCount, 0, 0),
    createdAt: String(payload.createdAt ?? ""),
    updatedAt: String(payload.updatedAt ?? ""),
  };
}

function normalizeForumPost(payload: Record<string, unknown>): ForumPost {
  const previewComments = Array.isArray(payload.previewComments)
    ? payload.previewComments
        .filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === "object")
        .map((item) => normalizeForumComment(item))
    : [];

  return {
    postId: toFiniteNumber(payload.postId, 0, 0),
    postUuid: String(payload.postUuid ?? ""),
    courseId: toFiniteNumber(payload.courseId, 0, 0),
    courseUuid: String(payload.courseUuid ?? ""),
    authorUserId: toFiniteNumber(payload.authorUserId, 0, 0),
    authorUserUuid: String(payload.authorUserUuid ?? ""),
    authorEmail: String(payload.authorEmail ?? ""),
    authorName: String(payload.authorName ?? "Unknown author"),
    title: payload.title == null ? null : String(payload.title),
    content: String(payload.content ?? ""),
    postKind: String(payload.postKind ?? "user"),
    metadataJson:
      payload.metadataJson && typeof payload.metadataJson === "object"
        ? (payload.metadataJson as Record<string, unknown>)
        : null,
    isPinned: Boolean(payload.isPinned),
    pinnedAt: payload.pinnedAt == null ? null : String(payload.pinnedAt),
    commentCount: toFiniteNumber(payload.commentCount, 0, 0),
    previewComments,
    createdAt: String(payload.createdAt ?? ""),
    updatedAt: String(payload.updatedAt ?? ""),
  };
}

function normalizePaginatedPosts(payload: unknown): PaginatedForumPostResponse {
  if (!payload || typeof payload !== "object") {
    return { items: [], page: 1, pageSize: 20, total: 0, totalPages: 1 };
  }

  const data = payload as Record<string, unknown>;
  const items = Array.isArray(data.items)
    ? data.items
        .filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === "object")
        .map((item) => normalizeForumPost(item))
    : [];

  return {
    items,
    page: toFiniteNumber(data.page, 1, 1),
    pageSize: toFiniteNumber(data.pageSize, 20, 1),
    total: toFiniteNumber(data.total, items.length, 0),
    totalPages: toFiniteNumber(data.totalPages, 1, 1),
  };
}

function normalizePaginatedComments(payload: unknown): PaginatedForumCommentResponse {
  if (!payload || typeof payload !== "object") {
    return { items: [], page: 1, pageSize: 20, total: 0, totalPages: 1 };
  }

  const data = payload as Record<string, unknown>;
  const items = Array.isArray(data.items)
    ? data.items
        .filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === "object")
        .map((item) => normalizeForumComment(item))
    : [];

  return {
    items,
    page: toFiniteNumber(data.page, 1, 1),
    pageSize: toFiniteNumber(data.pageSize, 20, 1),
    total: toFiniteNumber(data.total, items.length, 0),
    totalPages: toFiniteNumber(data.totalPages, 1, 1),
  };
}

async function parseResponse(response: Response, fallbackMessage: string) {
  const text = await response.text();
  const payload = parseJsonText(text);
  handleAuthenticationFailureFromResponse(response.status, payload);

  if (!response.ok) {
    throw new Error(extractErrorMessage(payload, fallbackMessage));
  }

  return payload;
}

export async function listCourseForumPosts(
  courseUuid: string,
  page = 1,
  pageSize = 20,
  query?: string
): Promise<PaginatedForumPostResponse> {
  const params = new URLSearchParams({ page: String(page), pageSize: String(pageSize) });
  const normalizedQuery = query?.trim() ?? "";
  if (normalizedQuery) {
    params.set("query", normalizedQuery);
  }
  const response = await fetch(
    `${COMMUNICATION_API_BASE_URL}/courses/${courseUuid}/forum-posts?${params.toString()}`,
    {
      method: "GET",
      headers: buildAuthHeaders({ "Content-Type": "application/json" }),
    }
  );

  return normalizePaginatedPosts(await parseResponse(response, "加载论坛帖子失败。"));
}

export async function createCourseForumPost(
  courseUuid: string,
  payload: CreateForumPostPayload
): Promise<ForumPost> {
  const response = await fetch(`${COMMUNICATION_API_BASE_URL}/courses/${courseUuid}/forum-posts`, {
    method: "POST",
    headers: buildAuthHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({
      title: payload.title?.trim() || null,
      content: payload.content.trim(),
      postKind: payload.postKind ?? "user",
      metadataJson: payload.metadataJson ?? null,
    }),
  });

  return normalizeForumPost(
    (await parseResponse(response, "创建论坛帖子失败。")) as Record<string, unknown>
  );
}

export async function getCourseForumPost(postUuid: string): Promise<ForumPost> {
  const response = await fetch(`${COMMUNICATION_API_BASE_URL}/forum-posts/${postUuid}`, {
    method: "GET",
    headers: buildAuthHeaders({ "Content-Type": "application/json" }),
  });

  return normalizeForumPost(
    (await parseResponse(response, "加载论坛帖子失败。")) as Record<string, unknown>
  );
}

export async function updateCourseForumPost(
  postUuid: string,
  payload: UpdateForumPostPayload
): Promise<ForumPost> {
  const response = await fetch(`${COMMUNICATION_API_BASE_URL}/forum-posts/${postUuid}`, {
    method: "PATCH",
    headers: buildAuthHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({
      title: payload.title === undefined ? undefined : payload.title?.trim() || null,
      content: payload.content === undefined ? undefined : payload.content.trim(),
      metadataJson: payload.metadataJson ?? undefined,
    }),
  });

  return normalizeForumPost(
    (await parseResponse(response, "更新论坛帖子失败。")) as Record<string, unknown>
  );
}

export async function deleteCourseForumPost(postUuid: string): Promise<void> {
  const response = await fetch(`${COMMUNICATION_API_BASE_URL}/forum-posts/${postUuid}`, {
    method: "DELETE",
    headers: buildAuthHeaders({ "Content-Type": "application/json" }),
  });

  await parseResponse(response, "删除论坛帖子失败。");
}

export async function pinCourseForumPost(postUuid: string): Promise<ForumPost> {
  const response = await fetch(`${COMMUNICATION_API_BASE_URL}/forum-posts/${postUuid}/pin`, {
    method: "POST",
    headers: buildAuthHeaders({ "Content-Type": "application/json" }),
  });

  return normalizeForumPost(
    (await parseResponse(response, "置顶论坛帖子失败。")) as Record<string, unknown>
  );
}

export async function unpinCourseForumPost(postUuid: string): Promise<ForumPost> {
  const response = await fetch(`${COMMUNICATION_API_BASE_URL}/forum-posts/${postUuid}/pin`, {
    method: "DELETE",
    headers: buildAuthHeaders({ "Content-Type": "application/json" }),
  });

  return normalizeForumPost(
    (await parseResponse(response, "取消置顶论坛帖子失败。")) as Record<string, unknown>
  );
}

export async function listForumComments(
  postUuid: string,
  page = 1,
  pageSize = 20
): Promise<PaginatedForumCommentResponse> {
  const params = new URLSearchParams({ page: String(page), pageSize: String(pageSize) });
  const response = await fetch(
    `${COMMUNICATION_API_BASE_URL}/forum-posts/${postUuid}/comments?${params.toString()}`,
    {
      method: "GET",
      headers: buildAuthHeaders({ "Content-Type": "application/json" }),
    }
  );

  return normalizePaginatedComments(await parseResponse(response, "加载评论失败。"));
}

export async function createForumComment(
  postUuid: string,
  payload: CreateForumCommentPayload
): Promise<ForumComment> {
  const response = await fetch(`${COMMUNICATION_API_BASE_URL}/forum-posts/${postUuid}/comments`, {
    method: "POST",
    headers: buildAuthHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({
      content: payload.content.trim(),
      commentKind: payload.commentKind ?? "user",
      replyToCommentUuid: payload.replyToCommentUuid ?? null,
      metadataJson: payload.metadataJson ?? null,
    }),
  });

  return normalizeForumComment(
    (await parseResponse(response, "创建评论失败。")) as Record<string, unknown>
  );
}

export async function listForumReplies(
  commentUuid: string,
  page = 1,
  pageSize = 20
): Promise<PaginatedForumCommentResponse> {
  const params = new URLSearchParams({ page: String(page), pageSize: String(pageSize) });
  const response = await fetch(
    `${COMMUNICATION_API_BASE_URL}/forum-comments/${commentUuid}/replies?${params.toString()}`,
    {
      method: "GET",
      headers: buildAuthHeaders({ "Content-Type": "application/json" }),
    }
  );

  return normalizePaginatedComments(await parseResponse(response, "加载回复失败。"));
}

export async function updateForumComment(
  commentUuid: string,
  payload: UpdateForumCommentPayload
): Promise<ForumComment> {
  const response = await fetch(`${COMMUNICATION_API_BASE_URL}/forum-comments/${commentUuid}`, {
    method: "PATCH",
    headers: buildAuthHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({
      content: payload.content === undefined ? undefined : payload.content.trim(),
      metadataJson: payload.metadataJson ?? undefined,
    }),
  });

  return normalizeForumComment(
    (await parseResponse(response, "更新评论失败。")) as Record<string, unknown>
  );
}

export async function deleteForumComment(commentUuid: string): Promise<ForumComment> {
  const response = await fetch(`${COMMUNICATION_API_BASE_URL}/forum-comments/${commentUuid}`, {
    method: "DELETE",
    headers: buildAuthHeaders({ "Content-Type": "application/json" }),
  });

  return normalizeForumComment(
    (await parseResponse(response, "删除评论失败。")) as Record<string, unknown>
  );
}
