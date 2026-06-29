from collections import defaultdict

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.models.course_forum_comment import CourseForumComment, ForumCommentKind

_UNSET = object()


class CourseForumCommentRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, comment_id: int) -> CourseForumComment | None:
        return self.session.get(CourseForumComment, comment_id)

    def list_top_level_by_post(
        self,
        *,
        post_id: int,
        page: int = 1,
        page_size: int = 5,
    ) -> tuple[list[CourseForumComment], int, int, int]:
        stmt = (
            select(CourseForumComment)
            .where(
                CourseForumComment.post_id == post_id,
                CourseForumComment.root_comment_id.is_(None),
            )
            .order_by(CourseForumComment.created_at.asc(), CourseForumComment.comment_id.asc())
        )
        return self._paginate(stmt, page=page, page_size=page_size)

    def list_preview_top_level_by_post_ids(
        self,
        *,
        post_ids: list[int],
        limit_per_post: int = 2,
    ) -> dict[int, list[CourseForumComment]]:
        if not post_ids:
            return {}

        stmt = (
            select(CourseForumComment)
            .where(
                CourseForumComment.post_id.in_(post_ids),
                CourseForumComment.root_comment_id.is_(None),
            )
            .order_by(
                CourseForumComment.post_id.asc(),
                CourseForumComment.created_at.asc(),
                CourseForumComment.comment_id.asc(),
            )
        )

        grouped: dict[int, list[CourseForumComment]] = defaultdict(list)
        for comment in self.session.scalars(stmt):
            bucket = grouped[comment.post_id]
            if len(bucket) < limit_per_post:
                bucket.append(comment)
        return dict(grouped)

    def list_replies_by_root_comment(
        self,
        *,
        root_comment_id: int,
        page: int = 1,
        page_size: int = 5,
    ) -> tuple[list[CourseForumComment], int, int, int]:
        stmt = (
            select(CourseForumComment)
            .where(CourseForumComment.root_comment_id == root_comment_id)
            .order_by(CourseForumComment.created_at.asc(), CourseForumComment.comment_id.asc())
        )
        return self._paginate(stmt, page=page, page_size=page_size)

    def count_by_post_ids(self, *, post_ids: list[int]) -> dict[int, int]:
        if not post_ids:
            return {}

        stmt = (
            select(CourseForumComment.post_id, func.count(CourseForumComment.comment_id))
            .where(CourseForumComment.post_id.in_(post_ids))
            .group_by(CourseForumComment.post_id)
        )
        return {int(post_id): int(total) for post_id, total in self.session.execute(stmt).all()}

    def count_replies_by_root_comment_ids(self, *, root_comment_ids: list[int]) -> dict[int, int]:
        if not root_comment_ids:
            return {}

        stmt = (
            select(CourseForumComment.root_comment_id, func.count(CourseForumComment.comment_id))
            .where(CourseForumComment.root_comment_id.in_(root_comment_ids))
            .group_by(CourseForumComment.root_comment_id)
        )
        return {
            int(root_comment_id): int(total)
            for root_comment_id, total in self.session.execute(stmt).all()
            if root_comment_id is not None
        }

    def create(
        self,
        *,
        post_id: int,
        course_id: int,
        author_user_id: int,
        author_email: str,
        author_name: str,
        content: str,
        comment_kind: ForumCommentKind = ForumCommentKind.USER,
        root_comment_id: int | None = None,
        reply_to_comment_id: int | None = None,
        metadata_json: dict | None = None,
    ) -> CourseForumComment:
        comment = CourseForumComment(
            post_id=post_id,
            course_id=course_id,
            author_user_id=author_user_id,
            author_email=author_email,
            author_name=author_name,
            root_comment_id=root_comment_id,
            reply_to_comment_id=reply_to_comment_id,
            content=content,
            comment_kind=comment_kind,
            metadata_json=metadata_json,
        )
        self.session.add(comment)
        self.session.flush()
        return comment

    def update(
        self,
        comment: CourseForumComment,
        *,
        content: str | object = _UNSET,
        metadata_json: dict | None | object = _UNSET,
        is_deleted: bool | object = _UNSET,
        deleted_at: object = _UNSET,
    ) -> CourseForumComment:
        if content is not _UNSET:
            comment.content = content
        if metadata_json is not _UNSET:
            comment.metadata_json = metadata_json
        if is_deleted is not _UNSET:
            comment.is_deleted = is_deleted
        if deleted_at is not _UNSET:
            comment.deleted_at = deleted_at
        self.session.flush()
        return comment

    def _paginate(
        self,
        stmt: Select[tuple[CourseForumComment]],
        *,
        page: int,
        page_size: int,
    ) -> tuple[list[CourseForumComment], int, int, int]:
        safe_page = max(1, page)
        safe_page_size = max(1, page_size)
        total = self.session.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
        total_pages = max(1, (total + safe_page_size - 1) // safe_page_size)
        bounded_page = min(safe_page, total_pages)
        offset = (bounded_page - 1) * safe_page_size
        items = list(self.session.scalars(stmt.offset(offset).limit(safe_page_size)))
        return items, total, bounded_page, total_pages
