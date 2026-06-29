export type ForumComment = {
  commentId: number;
  commentUuid: string;
  postId: number;
  postUuid: string;
  courseId: number;
  courseUuid: string;
  authorUserId: number;
  authorUserUuid: string;
  authorEmail: string;
  authorName: string;
  rootCommentId: number | null;
  rootCommentUuid: string | null;
  replyToCommentId: number | null;
  replyToCommentUuid: string | null;
  replyToAuthorName: string | null;
  content: string;
  commentKind: string;
  metadataJson: Record<string, unknown> | null;
  isDeleted: boolean;
  deletedAt: string | null;
  replyCount: number;
  createdAt: string;
  updatedAt: string;
};

export type ForumPost = {
  postId: number;
  postUuid: string;
  courseId: number;
  courseUuid: string;
  authorUserId: number;
  authorUserUuid: string;
  authorEmail: string;
  authorName: string;
  title: string | null;
  content: string;
  postKind: string;
  metadataJson: Record<string, unknown> | null;
  isPinned: boolean;
  pinnedAt: string | null;
  commentCount: number;
  previewComments: ForumComment[];
  createdAt: string;
  updatedAt: string;
};

export type PaginatedForumPostResponse = {
  items: ForumPost[];
  page: number;
  pageSize: number;
  total: number;
  totalPages: number;
};

export type PaginatedForumCommentResponse = {
  items: ForumComment[];
  page: number;
  pageSize: number;
  total: number;
  totalPages: number;
};

export type CreateForumPostPayload = {
  title?: string;
  content: string;
  postKind?: string;
  metadataJson?: Record<string, unknown> | null;
};

export type UpdateForumPostPayload = {
  title?: string | null;
  content?: string;
  metadataJson?: Record<string, unknown> | null;
};

export type CreateForumCommentPayload = {
  content: string;
  commentKind?: string;
  replyToCommentUuid?: string | null;
  metadataJson?: Record<string, unknown> | null;
};

export type UpdateForumCommentPayload = {
  content?: string;
  metadataJson?: Record<string, unknown> | null;
};
