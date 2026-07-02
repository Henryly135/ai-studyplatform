from datetime import datetime

from sqlalchemy.orm import Session

from app.core.uuid_codec import (
    decode_comment_uuid,
    encode_comment_uuid,
    encode_course_uuid,
    encode_forum_post_uuid,
    encode_user_uuid,
)
from app.models.course_forum_comment import CourseForumComment, ForumCommentKind
from app.repositories.course_forum_comment_repository import CourseForumCommentRepository, _UNSET
from app.repositories.course_forum_post_repository import CourseForumPostRepository
from app.services.course_forum_access_client import CourseForumAccessClient
from app.schemas.forum import (
    CourseForumCommentCreateRequest,
    CourseForumCommentRead,
    CourseForumCommentUpdateRequest,
    PaginatedCourseForumCommentResponse,
)
from platform_common.errors import (
    forum_comment_not_found_error,
    forum_comment_write_forbidden_error,
    forum_post_not_found_error,
    invalid_identity_response_error,
    invalid_request_error,
)


class ForumCommentService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.posts = CourseForumPostRepository(session)
        self.comments = CourseForumCommentRepository(session)
        self.course_access = CourseForumAccessClient()

    def create_comment(self, *, post_id: int, payload: CourseForumCommentCreateRequest, current_user: dict) -> CourseForumCommentRead:
        post = self.posts.get_by_id(post_id)
        if post is None:
            raise forum_post_not_found_error()
        self._ensure_forum_access_by_course_id(course_id=post.course_id, current_user=current_user)

        reply_to_comment = None
        root_comment_id = None
        reply_to_author_name = None
        author_user_id = self._require_current_user_id(current_user)
        if payload.replyToCommentUuid is not None:
            reply_to_comment = self._get_comment_or_404(decode_comment_uuid(payload.replyToCommentUuid))
            if reply_to_comment.post_id != post_id:
                raise invalid_request_error("replyToCommentUuid must belong to the same forum post")
            root_comment_id = reply_to_comment.comment_id if reply_to_comment.root_comment_id is None else reply_to_comment.root_comment_id
            reply_to_author_name = reply_to_comment.author_name

        comment = self.comments.create(
            post_id=post.post_id,
            course_id=post.course_id,
            author_user_id=author_user_id,
            author_email=self._normalize_required_text(str(current_user.get("email")), field_name="email"),
            author_name=self._normalize_required_text(str(current_user.get("userName")), field_name="userName"),
            content=self._normalize_required_text(payload.content, field_name="content"),
            comment_kind=self._parse_comment_kind(payload.commentKind),
            root_comment_id=root_comment_id,
            reply_to_comment_id=reply_to_comment.comment_id if reply_to_comment is not None else None,
            metadata_json=payload.metadataJson,
        )
        self.session.commit()
        self.session.refresh(comment)
        return self._to_read(comment, reply_count=0, reply_to_author_name=reply_to_author_name)

    def list_post_comments(
        self,
        *,
        post_id: int,
        current_user: dict,
        page: int = 1,
        page_size: int = 5,
    ) -> PaginatedCourseForumCommentResponse:
        post = self.posts.get_by_id(post_id)
        if post is None:
            raise forum_post_not_found_error()
        self._ensure_forum_access_by_course_id(course_id=post.course_id, current_user=current_user)

        items, total, safe_page, total_pages = self.comments.list_top_level_by_post(
            post_id=post_id,
            page=page,
            page_size=page_size,
        )
        reply_count_map = self.comments.count_replies_by_root_comment_ids(
            root_comment_ids=[item.comment_id for item in items],
        )
        return PaginatedCourseForumCommentResponse(
            items=[
                self._to_read(item, reply_count=reply_count_map.get(item.comment_id, 0), reply_to_author_name=None)
                for item in items
            ],
            page=safe_page,
            pageSize=page_size,
            total=total,
            totalPages=total_pages,
        )

    def list_comment_replies(
        self,
        *,
        comment_id: int,
        current_user: dict,
        page: int = 1,
        page_size: int = 5,
    ) -> PaginatedCourseForumCommentResponse:
        root_comment = self._get_comment_or_404(comment_id)
        self._ensure_forum_access_by_course_id(course_id=root_comment.course_id, current_user=current_user)
        if root_comment.root_comment_id is not None:
            raise invalid_request_error("Replies can only be expanded from a top-level comment")

        items, total, safe_page, total_pages = self.comments.list_replies_by_root_comment(
            root_comment_id=comment_id,
            page=page,
            page_size=page_size,
        )

        reply_target_ids = [item.reply_to_comment_id for item in items if item.reply_to_comment_id is not None]
        reply_target_map = {
            target_id: self.comments.get_by_id(target_id)
            for target_id in set(reply_target_ids)
        }

        return PaginatedCourseForumCommentResponse(
            items=[
                self._to_read(
                    item,
                    reply_count=0,
                    reply_to_author_name=(
                        reply_target_map[item.reply_to_comment_id].author_name
                        if item.reply_to_comment_id is not None and reply_target_map.get(item.reply_to_comment_id) is not None
                        else None
                    ),
                )
                for item in items
            ],
            page=safe_page,
            pageSize=page_size,
            total=total,
            totalPages=total_pages,
        )

    def get_comment(self, *, comment_id: int, current_user: dict) -> CourseForumCommentRead:
        comment = self._get_comment_or_404(comment_id)
        self._ensure_forum_access_by_course_id(course_id=comment.course_id, current_user=current_user)
        reply_count = 0
        if comment.root_comment_id is None:
            reply_count = self.comments.count_replies_by_root_comment_ids(root_comment_ids=[comment.comment_id]).get(
                comment.comment_id, 0
            )
        reply_to_author_name = None
        if comment.reply_to_comment_id is not None:
            reply_to_comment = self.comments.get_by_id(comment.reply_to_comment_id)
            reply_to_author_name = reply_to_comment.author_name if reply_to_comment is not None else None
        return self._to_read(comment, reply_count=reply_count, reply_to_author_name=reply_to_author_name)

    def update_comment(self, *, comment_id: int, payload: CourseForumCommentUpdateRequest, current_user: dict) -> CourseForumCommentRead:
        comment = self._get_comment_or_404(comment_id)
        self._ensure_forum_access_by_course_id(course_id=comment.course_id, current_user=current_user)
        self._ensure_comment_write_access(comment, current_user=current_user)
        if comment.is_deleted:
            raise invalid_request_error("Deleted comments cannot be edited")
        if payload.content is None and payload.metadataJson is None:
            raise invalid_request_error("At least one field must be provided for update")

        updated_comment = self.comments.update(
            comment,
            content=self._normalize_required_text(payload.content, field_name="content")
            if payload.content is not None
            else _UNSET,
            metadata_json=payload.metadataJson if payload.metadataJson is not None else _UNSET,
        )
        self.session.commit()
        self.session.refresh(updated_comment)
        return self.get_comment(comment_id=updated_comment.comment_id, current_user=current_user)

    def delete_comment(self, *, comment_id: int, deleted_at: datetime, current_user: dict) -> CourseForumCommentRead:
        comment = self._get_comment_or_404(comment_id)
        self._ensure_forum_access_by_course_id(course_id=comment.course_id, current_user=current_user)
        self._ensure_comment_write_access(comment, current_user=current_user)
        updated_comment = self.comments.update(
            comment,
            content="[deleted]",
            is_deleted=True,
            deleted_at=deleted_at,
        )
        self.session.commit()
        self.session.refresh(updated_comment)
        return self.get_comment(comment_id=updated_comment.comment_id, current_user=current_user)

    def _get_comment_or_404(self, comment_id: int) -> CourseForumComment:
        comment = self.comments.get_by_id(comment_id)
        if comment is None:
            raise forum_comment_not_found_error()
        return comment

    def _parse_comment_kind(self, value: str) -> ForumCommentKind:
        normalized = value.strip().lower()
        try:
            return ForumCommentKind(normalized)
        except ValueError as exc:
            raise invalid_request_error("commentKind must be one of user, system") from exc

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

    def _to_read(
        self,
        comment: CourseForumComment,
        *,
        reply_count: int,
        reply_to_author_name: str | None,
    ) -> CourseForumCommentRead:
        return CourseForumCommentRead(
            commentId=comment.comment_id,
            commentUuid=encode_comment_uuid(comment.comment_id),
            postId=comment.post_id,
            postUuid=encode_forum_post_uuid(comment.post_id),
            courseId=comment.course_id,
            courseUuid=encode_course_uuid(comment.course_id),
            authorUserId=comment.author_user_id,
            authorUserUuid=encode_user_uuid(comment.author_user_id),
            authorEmail=comment.author_email,
            authorName=comment.author_name,
            rootCommentId=comment.root_comment_id,
            rootCommentUuid=encode_comment_uuid(comment.root_comment_id) if comment.root_comment_id is not None else None,
            replyToCommentId=comment.reply_to_comment_id,
            replyToCommentUuid=encode_comment_uuid(comment.reply_to_comment_id) if comment.reply_to_comment_id is not None else None,
            replyToAuthorName=reply_to_author_name,
            content=comment.content,
            commentKind=comment.comment_kind.value,
            metadataJson=comment.metadata_json,
            isDeleted=comment.is_deleted,
            deletedAt=comment.deleted_at,
            replyCount=reply_count,
            createdAt=comment.created_at,
            updatedAt=comment.updated_at,
        )

    def _require_current_user_id(self, current_user: dict) -> int:
        user_id = current_user.get("id")
        if not isinstance(user_id, int):
            raise invalid_identity_response_error()
        return user_id

    def _ensure_forum_access_by_course_id(self, *, course_id: int, current_user: dict) -> None:
        self.course_access.assert_forum_access(
            course_uuid=encode_course_uuid(course_id),
            current_user=current_user,
        )

    def _ensure_comment_write_access(self, comment: CourseForumComment, *, current_user: dict) -> None:
        current_user_id = self._require_current_user_id(current_user)
        if comment.author_user_id == current_user_id:
            return
        if current_user.get("identity") == "Admin":
            return
        raise forum_comment_write_forbidden_error()
