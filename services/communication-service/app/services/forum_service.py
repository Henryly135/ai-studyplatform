from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.uuid_codec import encode_comment_uuid, encode_course_uuid, encode_forum_post_uuid, encode_user_uuid
from app.models.course_forum_post import CourseForumPost, ForumPostKind
from app.repositories.course_forum_comment_repository import CourseForumCommentRepository
from app.repositories.course_forum_post_repository import CourseForumPostRepository, _UNSET
from app.services.course_forum_access_client import CourseForumAccessClient
from app.services.course_management_client import CourseManagementClient
from app.schemas.forum import (
    CourseForumCommentRead,
    CourseForumPostCreateRequest,
    CourseForumPostRead,
    CourseForumPostUpdateRequest,
    PaginatedCourseForumPostResponse,
)
from platform_common.errors import (
    forum_post_pin_forbidden_error,
    forum_post_not_found_error,
    forum_post_write_forbidden_error,
    invalid_identity_response_error,
    invalid_request_error,
)


class ForumService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.posts = CourseForumPostRepository(session)
        self.comments = CourseForumCommentRepository(session)
        self.course_access = CourseForumAccessClient()
        self.course_management = CourseManagementClient()

    def create_post(self, *, course_id: int, payload: CourseForumPostCreateRequest, current_user: dict) -> CourseForumPostRead:
        self._ensure_forum_access_by_course_id(course_id=course_id, current_user=current_user)
        author_user_id = self._require_current_user_id(current_user)
        post = self.posts.create(
            course_id=course_id,
            author_user_id=author_user_id,
            author_email=self._normalize_required_text(str(current_user.get("email")), field_name="email"),
            author_name=self._normalize_required_text(str(current_user.get("userName")), field_name="userName"),
            title=self._normalize_optional_text(payload.title),
            content=self._normalize_required_text(payload.content, field_name="content"),
            post_kind=self._parse_post_kind(payload.postKind),
            metadata_json=payload.metadataJson,
        )
        self.session.commit()
        self.session.refresh(post)
        return self._to_read(post, comment_count=0, preview_comments=[])

    def list_posts(
        self,
        *,
        course_id: int,
        current_user: dict,
        query: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> PaginatedCourseForumPostResponse:
        self._ensure_forum_access_by_course_id(course_id=course_id, current_user=current_user)
        items, total, safe_page, total_pages = self.posts.list_by_course(
            course_id=course_id,
            query=query,
            page=page,
            page_size=page_size,
        )
        post_ids = [item.post_id for item in items]
        comment_count_map = self.comments.count_by_post_ids(post_ids=post_ids)
        preview_map = self.comments.list_preview_top_level_by_post_ids(post_ids=post_ids, limit_per_post=2)
        preview_comment_ids = [comment.comment_id for comments in preview_map.values() for comment in comments]
        reply_count_map = self.comments.count_replies_by_root_comment_ids(root_comment_ids=preview_comment_ids)

        return PaginatedCourseForumPostResponse(
            items=[
                self._to_read(
                    item,
                    comment_count=comment_count_map.get(item.post_id, 0),
                    preview_comments=[
                        self._to_comment_preview(comment, reply_count=reply_count_map.get(comment.comment_id, 0))
                        for comment in preview_map.get(item.post_id, [])
                    ],
                )
                for item in items
            ],
            page=safe_page,
            pageSize=page_size,
            total=total,
            totalPages=total_pages,
        )

    def get_post(self, *, post_id: int, current_user: dict) -> CourseForumPostRead:
        post = self._get_post_or_404(post_id)
        self._ensure_forum_access_by_course_id(course_id=post.course_id, current_user=current_user)
        comment_count = self.comments.count_by_post_ids(post_ids=[post_id]).get(post_id, 0)
        preview_comments = self.comments.list_preview_top_level_by_post_ids(post_ids=[post_id], limit_per_post=2).get(post_id, [])
        reply_count_map = self.comments.count_replies_by_root_comment_ids(
            root_comment_ids=[comment.comment_id for comment in preview_comments],
        )
        return self._to_read(
            post,
            comment_count=comment_count,
            preview_comments=[
                self._to_comment_preview(comment, reply_count=reply_count_map.get(comment.comment_id, 0))
                for comment in preview_comments
            ],
        )

    def update_post(self, *, post_id: int, payload: CourseForumPostUpdateRequest, current_user: dict) -> CourseForumPostRead:
        post = self._get_post_or_404(post_id)
        self._ensure_forum_access_by_course_id(course_id=post.course_id, current_user=current_user)
        self._ensure_post_write_access(post, current_user=current_user)

        if payload.title is None and payload.content is None and payload.metadataJson is None:
            raise invalid_request_error("At least one field must be provided for update")

        updated_post = self.posts.update(
            post,
            title=self._normalize_optional_text(payload.title) if payload.title is not None else _UNSET,
            content=self._normalize_required_text(payload.content, field_name="content")
            if payload.content is not None
            else _UNSET,
            metadata_json=payload.metadataJson if payload.metadataJson is not None else _UNSET,
        )
        self.session.commit()
        self.session.refresh(updated_post)
        return self.get_post(post_id=updated_post.post_id, current_user=current_user)

    def delete_post(self, *, post_id: int, current_user: dict) -> None:
        post = self._get_post_or_404(post_id)
        self._ensure_forum_access_by_course_id(course_id=post.course_id, current_user=current_user)
        self._ensure_post_write_access(post, current_user=current_user)
        self.posts.delete(post)
        self.session.commit()

    def pin_post(self, *, post_id: int, current_user: dict, token: str) -> CourseForumPostRead:
        post = self._get_post_or_404(post_id)
        self._ensure_forum_access_by_course_id(course_id=post.course_id, current_user=current_user)
        self._ensure_post_pin_access(post, current_user=current_user, token=token)
        actor_id = self._require_current_user_id(current_user)

        updated_post = self.posts.update(
            post,
            is_pinned=True,
            pinned_at=self._now_utc(),
            pinned_by_user_id=actor_id,
        )
        self.session.commit()
        self.session.refresh(updated_post)
        return self.get_post(post_id=updated_post.post_id, current_user=current_user)

    def unpin_post(self, *, post_id: int, current_user: dict, token: str) -> CourseForumPostRead:
        post = self._get_post_or_404(post_id)
        self._ensure_forum_access_by_course_id(course_id=post.course_id, current_user=current_user)
        self._ensure_post_pin_access(post, current_user=current_user, token=token)

        updated_post = self.posts.update(
            post,
            is_pinned=False,
            pinned_at=None,
            pinned_by_user_id=None,
        )
        self.session.commit()
        self.session.refresh(updated_post)
        return self.get_post(post_id=updated_post.post_id, current_user=current_user)

    def _get_post_or_404(self, post_id: int) -> CourseForumPost:
        post = self.posts.get_by_id(post_id)
        if post is None:
            raise forum_post_not_found_error()
        return post

    def _parse_post_kind(self, value: str) -> ForumPostKind:
        normalized = value.strip().lower()
        try:
            return ForumPostKind(normalized)
        except ValueError as exc:
            raise invalid_request_error("postKind must be one of user, system") from exc

    def _normalize_required_text(self, value: str | None, *, field_name: str) -> str:
        normalized = self._normalize_optional_text(value)
        if not normalized:
            raise invalid_request_error(f"{field_name} is required")
        return normalized

    def _normalize_optional_text(self, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    def _to_comment_preview(self, comment, *, reply_count: int) -> CourseForumCommentRead:
        return CourseForumCommentRead(
            commentId=comment.comment_id,
            commentUuid=encode_comment_uuid(comment.comment_id),
            postId=comment.post_id,
            postUuid=encode_forum_post_uuid(comment.post_id),
            courseId=comment.course_id,
            courseUuid=encode_course_uuid(comment.course_id),
            authorUserId=comment.author_user_id,
            authorUserUuid=encode_user_uuid(comment.author_user_id),
            authorEmail=self._redact_email(comment.author_email),
            authorName=comment.author_name,
            rootCommentId=comment.root_comment_id,
            rootCommentUuid=encode_comment_uuid(comment.root_comment_id) if comment.root_comment_id is not None else None,
            replyToCommentId=comment.reply_to_comment_id,
            replyToCommentUuid=encode_comment_uuid(comment.reply_to_comment_id) if comment.reply_to_comment_id is not None else None,
            replyToAuthorName=None,
            content=comment.content,
            commentKind=comment.comment_kind.value,
            metadataJson=comment.metadata_json,
            isDeleted=comment.is_deleted,
            deletedAt=comment.deleted_at,
            replyCount=reply_count,
            createdAt=comment.created_at,
            updatedAt=comment.updated_at,
        )

    def _to_read(
        self,
        post: CourseForumPost,
        *,
        comment_count: int,
        preview_comments: list[CourseForumCommentRead],
    ) -> CourseForumPostRead:
        return CourseForumPostRead(
            postId=post.post_id,
            postUuid=encode_forum_post_uuid(post.post_id),
            courseId=post.course_id,
            courseUuid=encode_course_uuid(post.course_id),
            authorUserId=post.author_user_id,
            authorUserUuid=encode_user_uuid(post.author_user_id),
            authorEmail=self._redact_email(post.author_email),
            authorName=post.author_name,
            title=post.title,
            content=post.content,
            postKind=post.post_kind.value,
            metadataJson=post.metadata_json,
            isPinned=post.is_pinned,
            pinnedAt=post.pinned_at,
            commentCount=comment_count,
            previewComments=preview_comments,
            createdAt=post.created_at,
            updatedAt=post.updated_at,
        )

    def _require_current_user_id(self, current_user: dict) -> int:
        user_id = current_user.get("id")
        if not isinstance(user_id, int):
            raise invalid_identity_response_error()
        return user_id

    def _redact_email(self, value: str | None) -> str:
        normalized = (value or "").strip()
        if "@" not in normalized:
            return ""
        local_part, domain = normalized.split("@", 1)
        if not local_part:
            return f"***@{domain}"
        return f"{local_part[0]}***@{domain}"

    def _ensure_forum_access_by_course_id(self, *, course_id: int, current_user: dict) -> None:
        self.course_access.assert_forum_access(
            course_uuid=encode_course_uuid(course_id),
            current_user=current_user,
        )

    def _ensure_post_write_access(self, post: CourseForumPost, *, current_user: dict) -> None:
        current_user_id = self._require_current_user_id(current_user)
        if post.author_user_id == current_user_id:
            return
        if current_user.get("identity") == "Admin":
            return
        raise forum_post_write_forbidden_error()

    def _ensure_post_pin_access(self, post: CourseForumPost, *, current_user: dict, token: str) -> None:
        identity = current_user.get("identity")
        if identity == "Admin":
            return
        if identity != "Educator":
            raise forum_post_pin_forbidden_error()

        self.course_management.assert_pin_access(
            course_uuid=encode_course_uuid(post.course_id),
            token=token,
        )

    def _now_utc(self) -> datetime:
        return datetime.now(timezone.utc).replace(tzinfo=None)
