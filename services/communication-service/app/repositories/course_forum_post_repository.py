from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.models.course_forum_post import CourseForumPost, ForumPostKind

_UNSET = object()


class CourseForumPostRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, post_id: int) -> CourseForumPost | None:
        return self.session.get(CourseForumPost, post_id)

    def list_by_course(
        self,
        *,
        course_id: int,
        query: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[CourseForumPost], int, int, int]:
        stmt = select(CourseForumPost).where(CourseForumPost.course_id == course_id)
        normalized_query = (query or "").strip()
        if normalized_query:
            search_pattern = f"%{normalized_query}%"
            stmt = stmt.where(
                CourseForumPost.title.ilike(search_pattern) | CourseForumPost.content.ilike(search_pattern)
            )

        stmt = stmt.order_by(
            CourseForumPost.is_pinned.desc(),
            CourseForumPost.pinned_at.desc(),
            CourseForumPost.created_at.desc(),
            CourseForumPost.post_id.desc(),
        )
        return self._paginate(stmt, page=page, page_size=page_size)

    def create(
        self,
        *,
        course_id: int,
        author_user_id: int,
        author_email: str,
        author_name: str,
        content: str,
        post_kind: ForumPostKind = ForumPostKind.USER,
        title: str | None = None,
        metadata_json: dict | None = None,
    ) -> CourseForumPost:
        post = CourseForumPost(
            course_id=course_id,
            author_user_id=author_user_id,
            author_email=author_email,
            author_name=author_name,
            content=content,
            post_kind=post_kind,
            title=title,
            metadata_json=metadata_json,
        )
        self.session.add(post)
        self.session.flush()
        return post

    def update(
        self,
        post: CourseForumPost,
        *,
        title: str | None | object = _UNSET,
        content: str | object = _UNSET,
        metadata_json: dict | None | object = _UNSET,
        is_pinned: bool | object = _UNSET,
        pinned_at: object = _UNSET,
        pinned_by_user_id: int | None | object = _UNSET,
    ) -> CourseForumPost:
        if title is not _UNSET:
            post.title = title
        if content is not _UNSET:
            post.content = content
        if metadata_json is not _UNSET:
            post.metadata_json = metadata_json
        if is_pinned is not _UNSET:
            post.is_pinned = is_pinned
        if pinned_at is not _UNSET:
            post.pinned_at = pinned_at
        if pinned_by_user_id is not _UNSET:
            post.pinned_by_user_id = pinned_by_user_id
        self.session.flush()
        return post

    def delete(self, post: CourseForumPost) -> None:
        self.session.delete(post)
        self.session.flush()

    def _paginate(
        self,
        stmt: Select[tuple[CourseForumPost]],
        *,
        page: int,
        page_size: int,
    ) -> tuple[list[CourseForumPost], int, int, int]:
        safe_page = max(1, page)
        safe_page_size = max(1, page_size)
        total = self.session.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
        total_pages = max(1, (total + safe_page_size - 1) // safe_page_size)
        bounded_page = min(safe_page, total_pages)
        offset = (bounded_page - 1) * safe_page_size
        items = list(self.session.scalars(stmt.offset(offset).limit(safe_page_size)))
        return items, total, bounded_page, total_pages
