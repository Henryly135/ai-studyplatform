import { useCallback, useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { LuPin, LuSearch, LuX } from "react-icons/lu";
import { useOutletContext } from "react-router-dom";

import { getStoredCurrentUser } from "../../services/api";
import {
  createCourseForumPost,
  createForumComment,
  deleteCourseForumPost,
  deleteForumComment,
  listCourseForumPosts,
  listForumComments,
  listForumReplies,
  pinCourseForumPost,
  unpinCourseForumPost,
} from "../../services/forum";
import type { ForumComment, ForumPost } from "../../types/forum";
import type { CourseOutletContext } from "./CourseLayout";

type RepliesByComment = Record<string, ForumComment[]>;
type ReplyDrafts = Record<string, string>;
type ReplyLoadingMap = Record<string, boolean>;
type CommentsByPost = Record<string, ForumComment[]>;
type PostCommentLoadingMap = Record<string, boolean>;
type CommentDraftsByPost = Record<string, string>;
type ReplyTargetByPost = Record<string, string | null>;
type ExpandedCommentsByPost = Record<string, boolean>;
type OpenCommentComposerByPost = Record<string, boolean>;
type ExpandedThreadsByPost = Record<string, boolean>;
type CommentPaginationState = {
  page: number;
  pageSize: number;
  total: number;
  totalPages: number;
};
type CommentPaginationByPost = Record<string, CommentPaginationState>;
type ReplyPaginationByComment = Record<string, CommentPaginationState>;
type PostPaginationState = {
  page: number;
  pageSize: number;
  total: number;
  totalPages: number;
};
type PendingForumDelete =
  | {
      kind: "post";
      post: ForumPost;
    }
  | {
      kind: "comment";
      post: ForumPost;
      comment: ForumComment;
      parentComment?: ForumComment;
    };

const POSTS_PAGE_SIZE = 10;

function formatForumTimestamp(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "刚刚";
  }

  return date.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function getAvatarInitials(name: string) {
  const parts = name
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2);

  if (parts.length === 0) {
    return "?";
  }

  return parts.map((part) => part[0]?.toUpperCase() ?? "").join("");
}

function isEducatorAuthor(authorUserId: number, educatorId?: number) {
  return typeof educatorId === "number" && educatorId > 0 && authorUserId === educatorId;
}

function getAuthorRoleBadge(authorUserId: number, educatorId?: number) {
  if (isEducatorAuthor(authorUserId, educatorId)) {
    return { label: "教师", className: "course-forum-role-badge" };
  }

  return {
    label: "学生",
    className: "course-forum-role-badge course-forum-role-badge-student",
  };
}

function sortForumPosts(items: ForumPost[]) {
  return [...items].sort((left, right) => {
    if (left.isPinned !== right.isPinned) {
      return left.isPinned ? -1 : 1;
    }

    const leftPinnedAt = left.pinnedAt ? new Date(left.pinnedAt).getTime() : 0;
    const rightPinnedAt = right.pinnedAt ? new Date(right.pinnedAt).getTime() : 0;
    if (left.isPinned && right.isPinned && leftPinnedAt !== rightPinnedAt) {
      return rightPinnedAt - leftPinnedAt;
    }

    const leftCreatedAt = new Date(left.createdAt).getTime();
    const rightCreatedAt = new Date(right.createdAt).getTime();
    return rightCreatedAt - leftCreatedAt;
  });
}

function getForumPostSnippet(post: ForumPost) {
  const source = (post.content || post.title || "").trim();
  if (source.length <= 96) {
    return source;
  }
  return `${source.slice(0, 96).trim()}...`;
}

function escapeRegExp(value: string) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function renderHighlightedText(text: string, query: string) {
  const normalizedQuery = query.trim();
  if (!normalizedQuery) {
    return text;
  }

  const pattern = new RegExp(`(${escapeRegExp(normalizedQuery)})`, "ig");
  const parts = text.split(pattern);

  return parts.map((part, index) =>
    part.toLowerCase() === normalizedQuery.toLowerCase() ? (
      <mark key={`${part}-${index}`} className="course-forum-search-highlight">
        {part}
      </mark>
    ) : (
      part
    )
  );
}

function CourseForumPage() {
  const { course, forumCoursesLoading, forumCoursesError } = useOutletContext<CourseOutletContext>();
  const [currentUser] = useState(() => getStoredCurrentUser());

  const [posts, setPosts] = useState<ForumPost[]>([]);
  const [postsLoading, setPostsLoading] = useState(false);
  const [postsError, setPostsError] = useState<string | null>(null);
  const [postsPagination, setPostsPagination] = useState<PostPaginationState>({
    page: 0,
    pageSize: POSTS_PAGE_SIZE,
    total: 0,
    totalPages: 1,
  });
  const [isLoadingMorePosts, setIsLoadingMorePosts] = useState(false);
  const [isSearchModalOpen, setIsSearchModalOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<ForumPost[]>([]);
  const [searchResultsLoading, setSearchResultsLoading] = useState(false);
  const [searchResultsError, setSearchResultsError] = useState<string | null>(null);
  const [highlightedPostUuid, setHighlightedPostUuid] = useState<string | null>(null);
  const [pendingScrollPostUuid, setPendingScrollPostUuid] = useState<string | null>(null);
  const [postTitle, setPostTitle] = useState("");
  const [postContent, setPostContent] = useState("");
  const [postFormError, setPostFormError] = useState<string | null>(null);
  const [isPosting, setIsPosting] = useState(false);
  const [isComposerOpen, setIsComposerOpen] = useState(false);

  const [commentsError, setCommentsError] = useState<string | null>(null);
  const [commentDraftsByPost, setCommentDraftsByPost] = useState<CommentDraftsByPost>({});
  const [replyTargetByPost, setReplyTargetByPost] = useState<ReplyTargetByPost>({});
  const [replyDrafts, setReplyDrafts] = useState<ReplyDrafts>({});
  const [isCommentSubmitting, setIsCommentSubmitting] = useState(false);
  const [repliesByComment, setRepliesByComment] = useState<RepliesByComment>({});
  const [replyLoadingMap, setReplyLoadingMap] = useState<ReplyLoadingMap>({});
  const [replyPaginationByComment, setReplyPaginationByComment] = useState<ReplyPaginationByComment>({});
  const [commentsByPost, setCommentsByPost] = useState<CommentsByPost>({});
  const [postCommentLoadingMap, setPostCommentLoadingMap] = useState<PostCommentLoadingMap>({});
  const [expandedCommentsByPost, setExpandedCommentsByPost] = useState<ExpandedCommentsByPost>({});
  const [expandedThreadsByPost, setExpandedThreadsByPost] = useState<ExpandedThreadsByPost>({});
  const [openCommentComposerByPost, setOpenCommentComposerByPost] =
    useState<OpenCommentComposerByPost>({});
  const [commentPaginationByPost, setCommentPaginationByPost] = useState<CommentPaginationByPost>({});
  const [pinningPostUuid, setPinningPostUuid] = useState<string | null>(null);
  const [deletingPostUuid, setDeletingPostUuid] = useState<string | null>(null);
  const [deletingCommentUuid, setDeletingCommentUuid] = useState<string | null>(null);
  const [pendingForumDelete, setPendingForumDelete] = useState<PendingForumDelete | null>(null);
  const loadMoreTriggerRef = useRef<HTMLDivElement | null>(null);
  const postsRequestKeyRef = useRef("");
  const loadingMorePostsRef = useRef(false);
  const postElementRefs = useRef<Record<string, HTMLElement | null>>({});
  const searchTriggerRef = useRef<HTMLButtonElement | null>(null);
  const highlightedPostFocusRestoreRef = useRef<(() => void) | null>(null);

  const canPinPosts = currentUser?.identity === "Educator" || currentUser?.identity === "Admin";
  const hasMorePosts = postsPagination.page < postsPagination.totalPages;
  const canDeleteAuthoredContent = (authorUserId: number) =>
    currentUser?.identity === "Admin" || currentUser?.id === authorUserId;
  const closeSearchModal = useCallback((options?: { restoreFocus?: boolean }) => {
    setIsSearchModalOpen(false);
    if (options?.restoreFocus === false) {
      return;
    }

    window.setTimeout(() => {
      searchTriggerRef.current?.focus();
    }, 0);
  }, []);

  useEffect(() => {
    let cancelled = false;
    const requestKey = `${course.courseUuid}::feed`;
    postsRequestKeyRef.current = requestKey;

    const loadPosts = async () => {
      setPostsLoading(true);
      setIsLoadingMorePosts(false);
      loadingMorePostsRef.current = false;
      setPostsError(null);
      setCommentsError(null);
      setCommentsByPost({});
      setCommentPaginationByPost({});
      setPostCommentLoadingMap({});
      setExpandedCommentsByPost({});
      setExpandedThreadsByPost({});
      setOpenCommentComposerByPost({});
      setReplyTargetByPost({});
      setReplyDrafts({});
      setRepliesByComment({});
      setReplyPaginationByComment({});
      setReplyLoadingMap({});

      try {
        const data = await listCourseForumPosts(course.courseUuid, 1, POSTS_PAGE_SIZE);
        if (!cancelled && postsRequestKeyRef.current === requestKey) {
          setPosts(sortForumPosts(data.items));
          setPostsPagination({
            page: data.page,
            pageSize: data.pageSize,
            total: data.total,
            totalPages: data.totalPages,
          });
        }
      } catch (error) {
        if (!cancelled && postsRequestKeyRef.current === requestKey) {
          setPosts([]);
          setPostsPagination({
            page: 0,
            pageSize: POSTS_PAGE_SIZE,
            total: 0,
            totalPages: 1,
          });
          setPostsError(error instanceof Error ? error.message : "Failed to load forum posts.");
        }
      } finally {
        if (!cancelled && postsRequestKeyRef.current === requestKey) {
          setPostsLoading(false);
        }
      }
    };

    void loadPosts();

    return () => {
      cancelled = true;
    };
  }, [course.courseUuid]);

  useEffect(() => {
    if (!pendingForumDelete) {
      return;
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape" || deletingPostUuid || deletingCommentUuid) {
        return;
      }

      setPendingForumDelete(null);
      setPostsError(null);
      setCommentsError(null);
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [deletingCommentUuid, deletingPostUuid, pendingForumDelete]);

  useEffect(() => {
    if (!isSearchModalOpen) {
      return;
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        closeSearchModal();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [closeSearchModal, isSearchModalOpen]);

  useEffect(() => {
    if (!isSearchModalOpen) {
      return;
    }

    const normalizedQuery = searchQuery.trim();
    if (!normalizedQuery) {
      setSearchResults([]);
      setSearchResultsError(null);
      setSearchResultsLoading(false);
      return;
    }

    let cancelled = false;
    setSearchResultsLoading(true);
    setSearchResultsError(null);

    const timeoutId = window.setTimeout(() => {
      void listCourseForumPosts(course.courseUuid, 1, 12, normalizedQuery)
        .then((data) => {
          if (cancelled) {
            return;
          }
          setSearchResults(data.items);
        })
        .catch((error) => {
          if (cancelled) {
            return;
          }
          setSearchResults([]);
          setSearchResultsError(error instanceof Error ? error.message : "Failed to search forum posts.");
        })
        .finally(() => {
          if (!cancelled) {
            setSearchResultsLoading(false);
          }
        });
    }, 220);

    return () => {
      cancelled = true;
      window.clearTimeout(timeoutId);
    };
  }, [course.courseUuid, isSearchModalOpen, searchQuery]);

  useEffect(() => {
    if (!pendingScrollPostUuid) {
      return;
    }

    const target = postElementRefs.current[pendingScrollPostUuid];
    if (!target) {
      return;
    }

    const focusedPostUuid = pendingScrollPostUuid;
    const previousTabIndex = target.getAttribute("tabindex");
    highlightedPostFocusRestoreRef.current?.();
    target.scrollIntoView({ behavior: "smooth", block: "center" });
    target.setAttribute("tabindex", "-1");
    target.focus({ preventScroll: true });
    highlightedPostFocusRestoreRef.current = () => {
      if (previousTabIndex === null) {
        target.removeAttribute("tabindex");
      } else {
        target.setAttribute("tabindex", previousTabIndex);
      }
    };
    setHighlightedPostUuid(focusedPostUuid);
    setPendingScrollPostUuid(null);
  }, [pendingScrollPostUuid, posts]);

  useEffect(() => {
    if (!highlightedPostUuid) {
      return;
    }

    const timeoutId = window.setTimeout(() => {
      setHighlightedPostUuid((current) => (current === highlightedPostUuid ? null : current));
      highlightedPostFocusRestoreRef.current?.();
      highlightedPostFocusRestoreRef.current = null;
    }, 2200);

    return () => {
      window.clearTimeout(timeoutId);
    };
  }, [highlightedPostUuid]);

  useEffect(() => {
    const node = loadMoreTriggerRef.current;
    if (!node || postsLoading || isLoadingMorePosts || !hasMorePosts) {
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        const firstEntry = entries[0];
        if (
          !firstEntry?.isIntersecting ||
          postsLoading ||
          isLoadingMorePosts ||
          loadingMorePostsRef.current ||
          !hasMorePosts
        ) {
          return;
        }

        const nextPage = postsPagination.page + 1;
        const requestKey = `${course.courseUuid}::feed`;
        loadingMorePostsRef.current = true;
        setIsLoadingMorePosts(true);
        setPostsError(null);

        void listCourseForumPosts(course.courseUuid, nextPage, postsPagination.pageSize)
          .then((data) => {
            if (postsRequestKeyRef.current !== requestKey) {
              return;
            }

            setPosts((current) => {
              const seen = new Set(current.map((item) => item.postUuid));
              const merged = [...current];
              data.items.forEach((item) => {
                if (!seen.has(item.postUuid)) {
                  merged.push(item);
                }
              });
              return sortForumPosts(merged);
            });
            setPostsPagination({
              page: data.page,
              pageSize: data.pageSize,
              total: data.total,
              totalPages: data.totalPages,
            });
          })
          .catch((error) => {
            if (postsRequestKeyRef.current !== requestKey) {
              return;
            }
            setPostsError(error instanceof Error ? error.message : "Failed to load more forum posts.");
          })
          .finally(() => {
            if (postsRequestKeyRef.current === requestKey) {
              loadingMorePostsRef.current = false;
              setIsLoadingMorePosts(false);
            }
          });
      },
      { rootMargin: "240px 0px" }
    );

    observer.observe(node);
    return () => observer.disconnect();
  }, [
    course.courseUuid,
    hasMorePosts,
    isLoadingMorePosts,
    postsLoading,
    postsPagination.page,
    postsPagination.pageSize,
  ]);

  const handleLoadCommentPage = async (post: ForumPost, page: number, force = false) => {
    const pagination = commentPaginationByPost[post.postUuid];
    const pageSize = pagination?.pageSize ?? 5;
    if (postCommentLoadingMap[post.postUuid] || (!force && commentsByPost[post.postUuid] && page === 1 && (pagination?.page ?? 0) === 1)) {
      return;
    }

    setPostCommentLoadingMap((current) => ({ ...current, [post.postUuid]: true }));
    setCommentsError(null);

    try {
      const data = await listForumComments(post.postUuid, page, pageSize);
      setCommentsByPost((current) => ({
        ...current,
        [post.postUuid]: data.items,
      }));
      setCommentPaginationByPost((current) => ({
        ...current,
        [post.postUuid]: {
          page: data.page,
          pageSize: data.pageSize,
          total: data.total,
          totalPages: data.totalPages,
        },
      }));
    } catch (error) {
      setCommentsError(error instanceof Error ? error.message : "Failed to load comments.");
    } finally {
      setPostCommentLoadingMap((current) => ({ ...current, [post.postUuid]: false }));
    }
  };

  const handleCreatePost = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const normalizedTitle = postTitle.trim();
    const normalizedContent = postContent.trim();

    if (isPosting) {
      return;
    }

    if (!normalizedTitle || !normalizedContent) {
      setPostFormError("Title and content are required.");
      return;
    }

    setIsPosting(true);
    setPostFormError(null);
    setPostsError(null);

    try {
      const created = await createCourseForumPost(course.courseUuid, {
        title: normalizedTitle,
        content: normalizedContent,
      });
      setPosts((current) => sortForumPosts([created, ...current]));
      setPostsPagination((current) => ({
        ...current,
        total: current.total + 1,
        totalPages: Math.max(1, Math.ceil((current.total + 1) / current.pageSize)),
      }));
      setPostTitle("");
      setPostContent("");
      setPostFormError(null);
      setIsComposerOpen(false);
    } catch (error) {
      setPostsError(error instanceof Error ? error.message : "Failed to create forum post.");
    } finally {
      setIsPosting(false);
    }
  };

  const handleTogglePinPost = async (post: ForumPost) => {
    if (pinningPostUuid) {
      return;
    }

    setPinningPostUuid(post.postUuid);
    setPostsError(null);

    try {
      const updated = post.isPinned
        ? await unpinCourseForumPost(post.postUuid)
        : await pinCourseForumPost(post.postUuid);

      setPosts((current) => {
        const next = current.map((item) => (item.postUuid === updated.postUuid ? updated : item));
        return sortForumPosts(next);
      });
    } catch (error) {
      setPostsError(error instanceof Error ? error.message : "Failed to update pinned post.");
    } finally {
      setPinningPostUuid(null);
    }
  };

  const openPostDelete = (post: ForumPost) => {
    if (deletingPostUuid) {
      return;
    }

    setPostsError(null);
    setPendingForumDelete({ kind: "post", post });
  };

  const openCommentDelete = (post: ForumPost, comment: ForumComment, parentComment?: ForumComment) => {
    if (deletingCommentUuid) {
      return;
    }

    setCommentsError(null);
    setPendingForumDelete({ kind: "comment", post, comment, parentComment });
  };

  const closeForumDelete = () => {
    if (deletingPostUuid || deletingCommentUuid) {
      return;
    }

    setPendingForumDelete(null);
    setPostsError(null);
    setCommentsError(null);
  };

  const handleDeletePost = async () => {
    if (!pendingForumDelete || pendingForumDelete.kind !== "post" || deletingPostUuid) {
      return;
    }

    const { post } = pendingForumDelete;
    setDeletingPostUuid(post.postUuid);
    setPostsError(null);

    try {
      await deleteCourseForumPost(post.postUuid);
      setPosts((current) => current.filter((item) => item.postUuid !== post.postUuid));
      setPostsPagination((current) => {
        const nextTotal = Math.max(0, current.total - 1);
        return {
          ...current,
          total: nextTotal,
          totalPages: Math.max(1, Math.ceil(nextTotal / current.pageSize)),
        };
      });
      setCommentsByPost((current) => {
        const next = { ...current };
        delete next[post.postUuid];
        return next;
      });
      setCommentPaginationByPost((current) => {
        const next = { ...current };
        delete next[post.postUuid];
        return next;
      });
      setPendingForumDelete(null);
    } catch (error) {
      setPostsError(error instanceof Error ? error.message : "Failed to delete forum post.");
    } finally {
      setDeletingPostUuid(null);
    }
  };

  const handleDeleteComment = async () => {
    if (!pendingForumDelete || pendingForumDelete.kind !== "comment" || deletingCommentUuid) {
      return;
    }

    const { post, comment, parentComment } = pendingForumDelete;
    setDeletingCommentUuid(comment.commentUuid);
    setCommentsError(null);

    try {
      const deleted = await deleteForumComment(comment.commentUuid);

      if (parentComment) {
        setRepliesByComment((current) => ({
          ...current,
          [parentComment.commentUuid]: (current[parentComment.commentUuid] ?? []).filter(
            (item) => item.commentUuid !== deleted.commentUuid
          ),
        }));
        setCommentsByPost((current) => ({
          ...current,
          [post.postUuid]: (current[post.postUuid] ?? []).map((item) =>
            item.commentUuid === parentComment.commentUuid
              ? {
                  ...item,
                  replyCount: Math.max(0, item.replyCount - 1),
                }
              : item
          ),
        }));
        setPosts((current) =>
          current.map((item) =>
            item.postUuid === post.postUuid
              ? {
                  ...item,
                  commentCount: Math.max(0, item.commentCount - 1),
                }
              : item
          )
        );
        setReplyPaginationByComment((current) => {
          const existing = current[parentComment.commentUuid];
          if (!existing) {
            return current;
          }

          return {
            ...current,
            [parentComment.commentUuid]: {
              ...existing,
              total: Math.max(0, existing.total - 1),
              totalPages: Math.max(
                1,
                Math.ceil(Math.max(0, existing.total - 1) / Math.max(1, existing.pageSize))
              ),
            },
          };
        });
        setPendingForumDelete(null);
        return;
      }

      setCommentsByPost((current) => ({
        ...current,
        [post.postUuid]: (current[post.postUuid] ?? []).filter((item) => item.commentUuid !== deleted.commentUuid),
      }));
      setCommentPaginationByPost((current) => {
        const existing = current[post.postUuid];
        if (!existing) {
          return current;
        }

        return {
          ...current,
          [post.postUuid]: {
            ...existing,
            total: Math.max(0, existing.total - 1),
            totalPages: Math.max(1, Math.ceil(Math.max(0, existing.total - 1) / Math.max(1, existing.pageSize))),
          },
        };
      });
      setPosts((current) =>
        current.map((item) =>
          item.postUuid === post.postUuid
            ? {
                ...item,
                commentCount: Math.max(0, item.commentCount - 1),
              }
            : item
        )
      );
      setPendingForumDelete(null);
    } catch (error) {
      setCommentsError(error instanceof Error ? error.message : "Failed to delete comment.");
    } finally {
      setDeletingCommentUuid(null);
    }
  };

  const handleSearchResultSelect = (post: ForumPost) => {
    closeSearchModal({ restoreFocus: false });
    setPosts((current) => {
      const exists = current.some((item) => item.postUuid === post.postUuid);
      return exists ? current : sortForumPosts([post, ...current]);
    });
    setPendingScrollPostUuid(post.postUuid);
  };

  const handleSubmitComment = async (event: FormEvent<HTMLFormElement>, post: ForumPost) => {
    event.preventDefault();
    const draft = commentDraftsByPost[post.postUuid]?.trim() ?? "";
    if (!draft || isCommentSubmitting) {
      return;
    }

    setIsCommentSubmitting(true);
    setCommentsError(null);

    try {
      const created = await createForumComment(post.postUuid, { content: draft });
      const existingPagination = commentPaginationByPost[post.postUuid];
      setPosts((current) =>
        current.map((item) =>
          item.postUuid === post.postUuid ? { ...item, commentCount: item.commentCount + 1 } : item
        )
      );
      setCommentsByPost((current) => ({
        ...current,
        [post.postUuid]: [created, ...(current[post.postUuid] ?? [])],
      }));
      setCommentPaginationByPost((current) => ({
        ...current,
        [post.postUuid]: existingPagination
          ? {
              ...existingPagination,
              total: existingPagination.total + 1,
            }
          : {
              page: 1,
              pageSize: 5,
              total: 1,
              totalPages: 1,
            },
      }));
      setCommentDraftsByPost((current) => ({ ...current, [post.postUuid]: "" }));
      setOpenCommentComposerByPost((current) => ({ ...current, [post.postUuid]: false }));
    } catch (error) {
      setCommentsError(error instanceof Error ? error.message : "Failed to post your comment.");
    } finally {
      setIsCommentSubmitting(false);
    }
  };

  const handleLoadReplies = async (commentUuid: string) => {
    if (repliesByComment[commentUuid]) {
      setRepliesByComment((current) => {
        const next = { ...current };
        delete next[commentUuid];
        return next;
      });
      setReplyPaginationByComment((current) => {
        const next = { ...current };
        delete next[commentUuid];
        return next;
      });
      return;
    }

    setReplyLoadingMap((current) => ({ ...current, [commentUuid]: true }));

    try {
      const data = await listForumReplies(commentUuid, 1, 5);
      setRepliesByComment((current) => ({ ...current, [commentUuid]: data.items }));
      setReplyPaginationByComment((current) => ({
        ...current,
        [commentUuid]: {
          page: data.page,
          pageSize: data.pageSize,
          total: data.total,
          totalPages: data.totalPages,
        },
      }));
    } catch (error) {
      setCommentsError(error instanceof Error ? error.message : "Failed to load replies.");
    } finally {
      setReplyLoadingMap((current) => ({ ...current, [commentUuid]: false }));
    }
  };

  const handleLoadReplyPage = async (commentUuid: string, page: number) => {
    const pagination = replyPaginationByComment[commentUuid];
    const pageSize = pagination?.pageSize ?? 5;
    if (replyLoadingMap[commentUuid]) {
      return;
    }

    setReplyLoadingMap((current) => ({ ...current, [commentUuid]: true }));
    setCommentsError(null);

    try {
      const data = await listForumReplies(commentUuid, page, pageSize);
      setRepliesByComment((current) => ({ ...current, [commentUuid]: data.items }));
      setReplyPaginationByComment((current) => ({
        ...current,
        [commentUuid]: {
          page: data.page,
          pageSize: data.pageSize,
          total: data.total,
          totalPages: data.totalPages,
        },
      }));
    } catch (error) {
      setCommentsError(error instanceof Error ? error.message : "Failed to load replies.");
    } finally {
      setReplyLoadingMap((current) => ({ ...current, [commentUuid]: false }));
    }
  };

  const handleSubmitReply = async (
    event: FormEvent<HTMLFormElement>,
    post: ForumPost,
    targetComment: ForumComment
  ) => {
    event.preventDefault();
    if (isCommentSubmitting) {
      return;
    }

    const content = replyDrafts[targetComment.commentUuid]?.trim() || "";
    if (!content) {
      return;
    }

    setIsCommentSubmitting(true);
    setCommentsError(null);

    try {
      const created = await createForumComment(post.postUuid, {
        content,
        replyToCommentUuid: targetComment.commentUuid,
      });
      const existingPagination = replyPaginationByComment[targetComment.commentUuid];
      setPosts((current) =>
        current.map((item) =>
          item.postUuid === post.postUuid ? { ...item, commentCount: item.commentCount + 1 } : item
        )
      );

      setRepliesByComment((current) => ({
        ...current,
        [targetComment.commentUuid]: [...(current[targetComment.commentUuid] ?? []), created],
      }));
      setCommentsByPost((current) => ({
        ...current,
        [post.postUuid]: (current[post.postUuid] ?? []).map((item) =>
          item.commentUuid === targetComment.commentUuid
            ? { ...item, replyCount: item.replyCount + 1 }
            : item
        ),
      }));
      setReplyPaginationByComment((current) => ({
        ...current,
        [targetComment.commentUuid]: existingPagination
          ? {
              ...existingPagination,
              total: existingPagination.total + 1,
            }
          : {
              page: 1,
              pageSize: 5,
              total: 1,
              totalPages: 1,
            },
      }));
      setReplyDrafts((current) => ({ ...current, [targetComment.commentUuid]: "" }));
      setReplyTargetByPost((current) => ({ ...current, [post.postUuid]: null }));
    } catch (error) {
      setCommentsError(error instanceof Error ? error.message : "Failed to post your reply.");
    } finally {
      setIsCommentSubmitting(false);
    }
  };

  const renderReplyNode = (post: ForumPost, parentComment: ForumComment, comment: ForumComment) => {
    if (comment.isDeleted) {
      return null;
    }

    const isReplying = replyTargetByPost[post.postUuid] === parentComment.commentUuid;
    const authorRoleBadge = getAuthorRoleBadge(comment.authorUserId, course.educatorId);
    const canDeleteComment = !comment.isDeleted && canDeleteAuthoredContent(comment.authorUserId);

    return (
      <div key={comment.commentUuid} className="course-forum-reply-item">
        <div className="course-forum-inline-comment-head">
          <div className="course-forum-avatar" aria-hidden="true">
            {getAvatarInitials(comment.authorName)}
          </div>
          <div className="course-forum-inline-comment-body">
            <div className="course-forum-post-meta">
              <span className="course-forum-author-chip">
                <strong>{comment.authorName}</strong>
                <span className={authorRoleBadge.className}>{authorRoleBadge.label}</span>
                <small>{comment.authorEmail}</small>
              </span>
              <span>{formatForumTimestamp(comment.createdAt)}</span>
            </div>
            {comment.replyToAuthorName ? (
              <p className="course-forum-reply-target">回复 <strong>@{comment.replyToAuthorName}</strong>
              </p>
            ) : null}
            <p>{comment.content}</p>
            <div className="course-forum-action-row">
              <button
                type="button"
                className="course-secondary-link"
                onClick={() =>
                  setReplyTargetByPost((current) => ({
                    ...current,
                    [post.postUuid]:
                      current[post.postUuid] === parentComment.commentUuid ? null : parentComment.commentUuid,
                  }))
                }
              >
                {isReplying ? "Cancel reply" : "Reply"}
              </button>
              {canDeleteComment ? (
                <button
                  type="button"
                  className="course-secondary-link course-secondary-link-danger"
                  onClick={() => openCommentDelete(post, comment, parentComment)}
                  disabled={deletingCommentUuid === comment.commentUuid}
                >
                  {deletingCommentUuid === comment.commentUuid ? "Deleting..." : "Delete"}
                </button>
              ) : null}
            </div>
          </div>
        </div>
      </div>
    );
  };

  const renderCommentNode = (post: ForumPost, comment: ForumComment) => {
    if (comment.isDeleted) {
      return null;
    }

    const authorRoleBadge = getAuthorRoleBadge(comment.authorUserId, course.educatorId);
    const replies = (repliesByComment[comment.commentUuid] ?? []).filter((reply) => !reply.isDeleted);
    const replyPagination = replyPaginationByComment[comment.commentUuid];
    const replyListVisible = Boolean(repliesByComment[comment.commentUuid]);
    const isReplying = replyTargetByPost[post.postUuid] === comment.commentUuid;
    const hasNextReplyPage =
      replyPagination !== undefined && replyPagination.page < replyPagination.totalPages;
    const hasPreviousReplyPage =
      replyPagination !== undefined && replyPagination.page > 1;
    const canDeleteComment = !comment.isDeleted && canDeleteAuthoredContent(comment.authorUserId);

    return (
      <article key={comment.commentUuid} className="course-forum-comment-card">
        <div className="course-forum-comment-main">
          <div className="course-forum-inline-comment-head">
            <div className="course-forum-avatar" aria-hidden="true">
              {getAvatarInitials(comment.authorName)}
            </div>
            <div className="course-forum-inline-comment-body">
              <div className="course-forum-post-meta">
                <span className="course-forum-author-chip">
                  <strong>{comment.authorName}</strong>
                  <span className={authorRoleBadge.className}>{authorRoleBadge.label}</span>
                  <small>{comment.authorEmail}</small>
                </span>
                <span>{formatForumTimestamp(comment.createdAt)}</span>
              </div>
              {comment.replyToAuthorName ? (
                <p className="course-forum-reply-target">回复 <strong>@{comment.replyToAuthorName}</strong>
                </p>
              ) : null}
              <p>{comment.content}</p>

              <div className="course-forum-action-row">
                <button
                  type="button"
                  className="course-secondary-link"
                  onClick={() =>
                    setReplyTargetByPost((current) => ({
                      ...current,
                      [post.postUuid]:
                        current[post.postUuid] === comment.commentUuid ? null : comment.commentUuid,
                    }))
                  }
                >
                  {isReplying ? "Cancel reply" : "Reply"}
                </button>
                <button
                  type="button"
                  className="course-secondary-link"
                  onClick={() => void handleLoadReplies(comment.commentUuid)}
                  disabled={replyLoadingMap[comment.commentUuid]}
                >
                  {replyLoadingMap[comment.commentUuid]
                    ? "Loading replies..."
                    : replyListVisible
                      ? "Hide replies"
                      : `View replies (${comment.replyCount})`}
                </button>
                {canDeleteComment ? (
                  <button
                    type="button"
                    className="course-secondary-link course-secondary-link-danger"
                    onClick={() => openCommentDelete(post, comment)}
                    disabled={deletingCommentUuid === comment.commentUuid}
                  >
                    {deletingCommentUuid === comment.commentUuid ? "Deleting..." : "Delete"}
                  </button>
                ) : null}
              </div>
            </div>
          </div>

          {isReplying ? (
            <form
              className="course-forum-reply-form"
              onSubmit={(event) => void handleSubmitReply(event, post, comment)}
            >
              <textarea
                value={replyDrafts[comment.commentUuid] ?? ""}
                onChange={(event) =>
                  setReplyDrafts((current) => ({
                    ...current,
                    [comment.commentUuid]: event.target.value,
                  }))
                }
                placeholder={`Reply to ${comment.authorName}...`}
                rows={3}
              />
              <div className="course-forum-action-row">
                <button type="submit" className="course-primary-link" disabled={isCommentSubmitting}>
                  {isCommentSubmitting ? "Sending..." : "Post reply"}
                </button>
              </div>
            </form>
          ) : null}

          {replyListVisible && replies.length > 0 ? (
            <div className="course-forum-reply-list">
              {replies.map((reply) => renderReplyNode(post, comment, reply))}
              {hasPreviousReplyPage || hasNextReplyPage ? (
                <div className="course-forum-expand-actions course-forum-reply-pagination">
                  {replyPagination ? (
                    <span className="course-forum-page-indicator">页码 {replyPagination.page}共 {replyPagination.totalPages}
                    </span>
                  ) : null}
                  {hasPreviousReplyPage ? (
                    <button
                      type="button"
                      className="course-forum-expand-link"
                      onClick={() =>
                        void handleLoadReplyPage(
                          comment.commentUuid,
                          Math.max(1, (replyPagination?.page ?? 1) - 1)
                        )
                      }
                    >上一页
                    </button>
                  ) : null}
                  {hasNextReplyPage ? (
                    <button
                      type="button"
                      className="course-forum-expand-link"
                      onClick={() =>
                        void handleLoadReplyPage(comment.commentUuid, (replyPagination?.page ?? 1) + 1)
                      }
                    >下一页
                    </button>
                  ) : null}
                </div>
              ) : null}
            </div>
          ) : null}
        </div>
      </article>
    );
  };

  const pendingDeleteTitle =
    pendingForumDelete?.kind === "post"
      ? pendingForumDelete.post.title || "Untitled discussion"
      : "this comment";
  const pendingDeleteDescription =
    pendingForumDelete?.kind === "post"
      ? "This will remove the discussion and its comments from the course forum."
      : pendingForumDelete?.parentComment
        ? "This will remove the reply from the discussion thread."
        : "This will remove the comment from the discussion thread.";
  const pendingDeleteError =
    pendingForumDelete?.kind === "post"
      ? postsError
      : pendingForumDelete?.kind === "comment"
        ? commentsError
        : null;
  const isDeletingPendingForumTarget =
    pendingForumDelete?.kind === "post"
      ? deletingPostUuid !== null
      : pendingForumDelete?.kind === "comment"
        ? deletingCommentUuid !== null
        : false;

  return (
    <section className="course-detail-page course-forum-page">
      <header className="course-layout-header course-forum-simple-header">
        <div className="course-layout-header-title-group">
          <span className="course-forum-header-label">课程论坛</span>
          <div className="course-layout-header-title-row">
            <h2>{course.title}</h2>
          </div>
        </div>

        <div className="course-layout-header-meta course-forum-header-meta">
          <span>
            {postsPagination.total}讨论{postsPagination.total === 1 ? "" : "s"}
          </span>
          <button
            ref={searchTriggerRef}
            type="button"
            className="course-icon-button course-forum-search-trigger"
            onClick={() => setIsSearchModalOpen(true)}
            aria-label="搜索帖子"
            aria-haspopup="dialog"
            aria-expanded={isSearchModalOpen}
            title="搜索帖子"
          >
            <LuSearch aria-hidden="true" />
          </button>
          <button
            type="button"
            className="course-primary-link course-forum-create-button"
            onClick={() => setIsComposerOpen(true)}
          >发布帖子
          </button>
        </div>
      </header>

      <div className="course-forum-shell">
        {forumCoursesLoading || forumCoursesError ? (
          <div className="course-forum-status-row">
            {forumCoursesLoading ? <span>正在加载课程论坛...</span> : null}
            {forumCoursesError ? <span className="course-forum-inline-error">{forumCoursesError}</span> : null}
          </div>
        ) : null}

        {postsError ? (
          <div className="course-forum-status-row">
            <span className="course-forum-inline-error">{postsError}</span>
          </div>
        ) : null}

        {isSearchModalOpen ? (
          <div className="course-forum-modal-backdrop" role="presentation" onClick={() => closeSearchModal()}>
            <div
              className="course-panel course-forum-search-modal"
              role="dialog"
              aria-modal="true"
              aria-labelledby="course-forum-search-title"
              aria-describedby="course-forum-search-description"
              onClick={(event) => event.stopPropagation()}
            >
              <h3 id="course-forum-search-title" className="course-sr-only">搜索课程论坛帖子
              </h3>
              <p id="course-forum-search-description" className="course-sr-only">搜索本课程论坛中的帖子标题和内容。按退出键可关闭搜索窗口。
              </p>
              <div className="course-forum-search-modal-head">
                <div className="course-forum-search-input-shell">
                  <LuSearch aria-hidden="true" />
                  <input
                    type="search"
                    value={searchQuery}
                    onChange={(event) => setSearchQuery(event.target.value)}
                    placeholder="搜索帖子..."
                    aria-label="搜索帖子"
                    autoFocus
                  />
                </div>
                {searchQuery.trim() ? (
                  <button
                    type="button"
                    className="course-forum-search-clear"
                    onClick={() => setSearchQuery("")}
                  >清除
                  </button>
                ) : null}
                  <button
                    type="button"
                    className="course-forum-search-close"
                    onClick={() => closeSearchModal()}
                    aria-label="关闭搜索"
                  >
                  <LuX aria-hidden="true" />
                </button>
              </div>
              <div className="course-forum-search-results" aria-live="polite">
                {searchResultsLoading ? <p className="course-forum-search-status">正在搜索帖子...</p> : null}
                {!searchResultsLoading && searchResultsError ? (
                  <p className="course-forum-search-status course-forum-inline-error">{searchResultsError}</p>
                ) : null}
                {!searchResultsLoading && !searchResultsError && !searchQuery.trim() ? (
                  <p className="course-forum-search-status">搜索本课程的帖子标题和内容。</p>
                ) : null}
                {!searchResultsLoading && !searchResultsError && searchQuery.trim() && searchResults.length === 0 ? (
                  <p className="course-forum-search-status">未找到匹配的帖子。</p>
                ) : null}
                {!searchResultsLoading && !searchResultsError && searchResults.length > 0
                  ? searchResults.map((post) => (
                      <button
                        key={post.postUuid}
                        type="button"
                        className="course-forum-search-result"
                        onClick={() => handleSearchResultSelect(post)}
                      >
                        <span className="course-forum-search-result-icon">
                          <LuSearch aria-hidden="true" />
                        </span>
                        <span className="course-forum-search-result-copy">
                          <strong>{renderHighlightedText(post.title || "Untitled discussion", searchQuery)}</strong>
                          <small>{renderHighlightedText(getForumPostSnippet(post), searchQuery)}</small>
                        </span>
                      </button>
                    ))
                  : null}
              </div>
            </div>
          </div>
        ) : null}

        {isComposerOpen ? (
          <div className="course-forum-modal-backdrop" onClick={() => setIsComposerOpen(false)}>
            <div
              className="course-panel course-forum-modal"
              onClick={(event) => event.stopPropagation()}
            >
              <div className="course-forum-modal-header">
                <div className="course-panel-heading">
                  <h3>发布帖子</h3>
                </div>
                <button
                  type="button"
                  className="course-secondary-link"
                  onClick={() => setIsComposerOpen(false)}
                >关闭
                </button>
              </div>

              <form className="course-forum-composer" onSubmit={handleCreatePost}>
                <input
                  type="text"
                  value={postTitle}
                  onChange={(event) => {
                    setPostTitle(event.target.value);
                    if (postFormError) {
                      setPostFormError(null);
                    }
                  }}
                  placeholder="帖子标题"
                  aria-label="帖子标题"
                  aria-invalid={!postTitle.trim() && Boolean(postFormError)}
                />
                <textarea
                  value={postContent}
                  onChange={(event) => {
                    setPostContent(event.target.value);
                    if (postFormError) {
                      setPostFormError(null);
                    }
                  }}
                  placeholder="分享本课程的问题或讨论话题..."
                  rows={6}
                  aria-label="帖子内容"
                  aria-invalid={!postContent.trim() && Boolean(postFormError)}
                />
                {postFormError ? <p className="course-forum-inline-error">{postFormError}</p> : null}

                <div className="course-forum-action-row">
                  <button type="submit" className="course-primary-link" disabled={isPosting}>
                    {isPosting ? "Posting..." : "发布帖子"}
                  </button>
                </div>
              </form>
            </div>
          </div>
        ) : null}

        <div className="course-forum-main">
          <div className="course-forum-post-list">
              {postsLoading ? (
                <div className="course-panel course-forum-empty-card">
                  <strong>正在加载讨论...</strong>
                </div>
              ) : null}

              {!postsLoading && posts.length === 0 ? (
                <div className="course-panel course-forum-empty-card">
                  <strong>暂无讨论</strong>
                  <p>点击发布按钮，为这门课程开启第一条讨论。</p>
                </div>
              ) : null}

              {posts.map((post) => (
                <article
                  key={post.postUuid}
                  ref={(node) => {
                    postElementRefs.current[post.postUuid] = node;
                  }}
                  className={`course-panel course-forum-post-card${highlightedPostUuid === post.postUuid ? " is-highlighted" : ""}`}
                >
                  {(() => {
                    const authorRoleBadge = getAuthorRoleBadge(post.authorUserId, course.educatorId);
                    const allComments = commentsByPost[post.postUuid] ?? [];
                    const pagination = commentPaginationByPost[post.postUuid];
                    const isThreadExpanded = expandedThreadsByPost[post.postUuid] ?? false;
                    const isExpanded = expandedCommentsByPost[post.postUuid] ?? false;
                    const visibleComments = isExpanded ? allComments : allComments.slice(0, 2);
                    const hiddenCommentCount = Math.max(0, allComments.length - 2);
                    const hasNextPage =
                      pagination !== undefined && pagination.page < pagination.totalPages;
                    const hasPreviousPage = pagination !== undefined && pagination.page > 1;
                    const canDeletePost = canDeleteAuthoredContent(post.authorUserId);

                    return (
                      <>
                  <div className="course-forum-post-head">
                    <div className="course-forum-avatar course-forum-avatar-post" aria-hidden="true">
                      {getAvatarInitials(post.authorName)}
                    </div>
                    <div className="course-forum-post-body">
                      <div className="course-forum-post-head-top">
                        <div className="course-forum-post-author-block">
                          <div className="course-forum-post-author-row">
                            <strong>{post.authorName}</strong>
                            <span className={authorRoleBadge.className}>{authorRoleBadge.label}</span>
                            <small>{post.authorEmail}</small>
                          </div>
                          <div className="course-forum-post-meta">
                            <span>{formatForumTimestamp(post.createdAt)}</span>
                          </div>
                        </div>
                        {canPinPosts ? (
                          <button
                            type="button"
                            className={`course-forum-pin-icon-button${post.isPinned ? " is-pinned" : ""}`}
                            disabled={pinningPostUuid === post.postUuid}
                            onClick={() => void handleTogglePinPost(post)}
                            aria-label={post.isPinned ? "Unpin post" : "Pin post"}
                            title={post.isPinned ? "Unpin post" : "Pin post"}
                          >
                            <LuPin aria-hidden="true" />
                          </button>
                        ) : post.isPinned ? (
                          <span
                            className="course-forum-pin-icon-indicator is-pinned"
                            aria-label="置顶帖子"
                            title="置顶帖子"
                          >
                            <LuPin aria-hidden="true" />
                          </span>
                        ) : null}
                      </div>
                    </div>
                  </div>
                  <div className="course-forum-post-title-link">
                    <h3>{post.title || "Untitled discussion"}</h3>
                  </div>
                  <p className="course-forum-post-content">{post.content}</p>
                  <div className="course-forum-post-actions-bar">
                    {canDeletePost ? (
                      <button
                        type="button"
                        className="course-secondary-link course-secondary-link-danger course-forum-post-delete-button"
                        onClick={() => openPostDelete(post)}
                        disabled={deletingPostUuid === post.postUuid}
                      >
                        {deletingPostUuid === post.postUuid ? "Deleting..." : "Delete"}
                      </button>
                    ) : null}
                    {isThreadExpanded ? (
                      <button
                        type="button"
                        className="course-secondary-link"
                        onClick={() =>
                          setOpenCommentComposerByPost((current) => ({
                            ...current,
                            [post.postUuid]: !current[post.postUuid],
                          }))
                        }
                      >
                        {openCommentComposerByPost[post.postUuid] ? "Cancel comment" : "Comment"}
                      </button>
                    ) : null}
                  </div>
                  {isThreadExpanded && openCommentComposerByPost[post.postUuid] ? (
                    <form
                      className="course-panel course-forum-comment-composer"
                      onSubmit={(event) => void handleSubmitComment(event, post)}
                    >
                      <div className="course-panel-heading">
                        <h3>评论这条帖子</h3>
                      </div>
                      <textarea
                        value={commentDraftsByPost[post.postUuid] ?? ""}
                        onChange={(event) =>
                          setCommentDraftsByPost((current) => ({
                            ...current,
                            [post.postUuid]: event.target.value,
                          }))
                        }
                        placeholder="写下你的评论..."
                        rows={3}
                      />
                      <div className="course-forum-action-row">
                        <button type="submit" className="course-primary-link" disabled={isCommentSubmitting}>
                          {isCommentSubmitting ? "Sending..." : "Post comment"}
                        </button>
                        {commentsError ? <span className="course-forum-inline-error">{commentsError}</span> : null}
                      </div>
                    </form>
                  ) : null}
                  {isThreadExpanded ? (
                  <div className="course-forum-comment-list">
                    {postCommentLoadingMap[post.postUuid] ? (
                      <div className="course-panel course-forum-empty-card">
                        <strong>正在加载评论...</strong>
                      </div>
                    ) : null}

                    {!postCommentLoadingMap[post.postUuid] &&
                    (commentsByPost[post.postUuid] ?? []).length === 0 ? (
                      <div className="course-panel course-forum-empty-card">
                        <strong>暂无评论</strong>
                        <p>成为第一个回复这条讨论的人。</p>
                      </div>
                    ) : null}

                    {visibleComments.map((comment) => renderCommentNode(post, comment))}

                    {!postCommentLoadingMap[post.postUuid] &&
                    (hiddenCommentCount > 0 || hasNextPage || hasPreviousPage) ? (
                      <div className="course-forum-expand-actions">
                        {hiddenCommentCount > 0 ? (
                          <button
                            type="button"
                            className="course-forum-expand-link"
                            onClick={() =>
                              setExpandedCommentsByPost((current) => ({
                                ...current,
                                [post.postUuid]: !isExpanded,
                              }))
                            }
                          >
                            {isExpanded
                              ? "Show fewer comments"
                              : `View ${hiddenCommentCount} more comment${hiddenCommentCount > 1 ? "s" : ""}`}
                          </button>
                        ) : null}

                        {isExpanded && pagination ? (
                          <span className="course-forum-page-indicator">页码 {pagination.page}共 {pagination.totalPages}
                          </span>
                        ) : null}

                        {isExpanded && hasPreviousPage ? (
                          <button
                            type="button"
                            className="course-forum-expand-link"
                            onClick={() =>
                              void handleLoadCommentPage(post, Math.max(1, (pagination?.page ?? 1) - 1))
                            }
                          >上一页
                          </button>
                        ) : null}

                        {isExpanded && hasNextPage ? (
                          <button
                            type="button"
                            className="course-forum-expand-link"
                            onClick={() =>
                              void handleLoadCommentPage(post, (pagination?.page ?? 1) + 1)
                            }
                          >下一页
                          </button>
                        ) : null}
                      </div>
                    ) : null}
                  </div>
                  ) : null}
                  <div className="course-forum-post-footer">
                    <strong>{post.commentCount}条评论</strong>
                    <button
                      type="button"
                      className="course-forum-expand-link"
                      onClick={() => {
                        const nextExpanded = !isThreadExpanded;
                        setExpandedThreadsByPost((current) => ({
                          ...current,
                          [post.postUuid]: nextExpanded,
                        }));
                        if (nextExpanded) {
                          void handleLoadCommentPage(post, 1);
                        } else {
                          setOpenCommentComposerByPost((current) => ({
                            ...current,
                            [post.postUuid]: false,
                          }));
                        }
                      }}
                    >
                      {isThreadExpanded
                        ? "Hide discussion"
                        : `View discussion${post.commentCount > 0 ? ` (${post.commentCount})` : ""}`}
                    </button>
                  </div>
                      </>
                    );
                  })()}
                </article>
              ))}
              {!postsLoading && posts.length > 0 ? (
                <div className="course-forum-list-status">
                  {isLoadingMorePosts ? <span>正在加载更多讨论...</span> : null}
                  {!hasMorePosts && postsPagination.total > postsPagination.pageSize ? (
                    <span>所有讨论已加载。</span>
                  ) : null}
                </div>
              ) : null}
              <div ref={loadMoreTriggerRef} className="course-forum-load-more-trigger" aria-hidden="true" />
            </div>
        </div>
      </div>

      {pendingForumDelete ? (
        <div className="course-confirm-modal-overlay" role="presentation">
          <div
            className="course-confirm-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="forum-delete-confirm-title"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="course-confirm-modal-header">
              <h3 id="forum-delete-confirm-title">
                {pendingForumDelete.kind === "post" ? "Delete discussion?" : "Delete comment?"}
              </h3>
              <p>{pendingDeleteTitle}</p>
            </div>

            <p className="course-confirm-modal-copy">{pendingDeleteDescription}</p>
            {pendingDeleteError ? (
              <p className="course-confirm-modal-error" role="alert">
                {pendingDeleteError}
              </p>
            ) : null}

            <div className="course-confirm-modal-actions">
              <button
                type="button"
                className="course-secondary-link"
                onClick={closeForumDelete}
                disabled={isDeletingPendingForumTarget}
              >返回
              </button>
              <button
                type="button"
                className="course-enroll-button"
                onClick={() =>
                  pendingForumDelete.kind === "post"
                    ? void handleDeletePost()
                    : void handleDeleteComment()
                }
                disabled={isDeletingPendingForumTarget}
              >
                {isDeletingPendingForumTarget ? "Deleting..." : "Delete"}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}

export default CourseForumPage;
