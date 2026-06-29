from datetime import datetime

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from app.core.time import now_local
from app.models.courses import Course, CourseStatus, DifficultyLevelStatus

_UNSET = object()


class CourseRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, course_id: int) -> Course | None:
        """Used by course-detail and management services to load a course by primary key."""
        return self.session.get(Course, course_id)

    def get_by_title(self, title: str) -> Course | None:
        """Used by catalog detail services to resolve a course by its display title."""
        stmt = select(Course).where(Course.title == title)
        return self.session.scalar(stmt)

    def list_all(self) -> list[Course]:
        """Used by admin and catalog services to fetch every course record."""
        stmt = select(Course).order_by(*self._course_order_by())
        return list(self.session.scalars(stmt))

    def list_all_paginated(
        self,
        *,
        search: str | None = None,
        page: int = 1,
        page_size: int = 20,
        offset: int | None = None,
    ) -> tuple[list[Course], int, int, int]:
        stmt = select(Course).order_by(*self._course_order_by())
        stmt = self._apply_search(stmt, search=search)
        return self._paginate(stmt, page=page, page_size=page_size, offset=offset)

    def list_by_educator(self, educator_id: int) -> list[Course]:
        """Used by educator dashboard services to list courses owned by an educator."""
        stmt = (
            select(Course)
            .where(Course.educator_id == educator_id)
            .order_by(*self._course_order_by())
        )
        return list(self.session.scalars(stmt))

    def list_by_educator_paginated(
        self,
        educator_id: int,
        *,
        search: str | None = None,
        page: int = 1,
        page_size: int = 20,
        offset: int | None = None,
    ) -> tuple[list[Course], int, int, int]:
        stmt = (
            select(Course)
            .where(Course.educator_id == educator_id)
            .order_by(*self._course_order_by())
        )
        stmt = self._apply_search(stmt, search=search)
        return self._paginate(stmt, page=page, page_size=page_size, offset=offset)

    def list_by_ids(self, course_ids: list[int]) -> list[Course]:
        if not course_ids:
            return []
        stmt = select(Course).where(Course.course_id.in_(course_ids)).order_by(*self._course_order_by())
        return list(self.session.scalars(stmt))

    def list_public_courses(self) -> list[Course]:
        """Used by learner catalog services to list publicly visible courses."""
        stmt = (
            select(Course)
            .where(Course.is_public.is_(True))
            .order_by(*self._course_order_by())
        )
        return list(self.session.scalars(stmt))

    def search_by_title_or_subtitle(self, query: str) -> list[Course]:
        """Used by course catalog search to fuzzy-match title and subtitle."""
        like_query = f"%{query.strip()}%"
        stmt = (
            select(Course)
            .where(
                Course.status == CourseStatus.PUBLISHED,
                or_(
                    Course.title.ilike(like_query),
                    Course.subtitle.ilike(like_query),
                ),
            )
            .order_by(*self._course_order_by())
        )
        return list(self.session.scalars(stmt))

    def list_by_status(self, status: CourseStatus) -> list[Course]:
        """Used by admin and publishing services to filter courses by workflow status."""
        stmt = (
            select(Course)
            .where(Course.status == status)
            .order_by(Course.updated_at.desc(), Course.course_id.desc())
        )
        return list(self.session.scalars(stmt))

    def list_by_status_paginated(
        self,
        status: CourseStatus,
        *,
        search: str | None = None,
        page: int = 1,
        page_size: int = 20,
        offset: int | None = None,
    ) -> tuple[list[Course], int, int, int]:
        stmt = (
            select(Course)
            .where(Course.status == status)
            .order_by(Course.updated_at.desc(), Course.course_id.desc())
        )
        stmt = self._apply_search(stmt, search=search)
        return self._paginate(stmt, page=page, page_size=page_size, offset=offset)

    def _apply_search(self, stmt: Select[tuple[Course]], *, search: str | None) -> Select[tuple[Course]]:
        if not search:
            return stmt

        normalized_search = search.strip()
        if not normalized_search:
            return stmt

        like_query = f"%{normalized_search}%"
        return stmt.where(
            or_(
                Course.title.ilike(like_query),
                Course.subtitle.ilike(like_query),
                Course.description.ilike(like_query),
                Course.category.ilike(like_query),
            )
        )

    def _course_order_by(self):
        return (
            Course.updated_at.desc(),
            Course.course_id.desc(),
        )

    def _paginate(
        self,
        stmt: Select[tuple[Course]],
        *,
        page: int,
        page_size: int,
        offset: int | None = None,
    ) -> tuple[list[Course], int, int, int]:
        normalized_page = max(1, page)
        normalized_page_size = max(1, page_size)
        total = self.session.scalar(
            select(func.count()).select_from(stmt.order_by(None).subquery())
        ) or 0
        total_pages = max(1, (total + normalized_page_size - 1) // normalized_page_size)
        safe_page = normalized_page if offset is not None else min(normalized_page, total_pages)
        safe_offset = max(0, offset) if offset is not None else (safe_page - 1) * normalized_page_size
        items = list(self.session.scalars(stmt.offset(safe_offset).limit(normalized_page_size)))
        return items, total, safe_page, total_pages

    def create(
        self,
        *,
        educator_id: int,
        title: str,
        subtitle: str | None = None,
        description: str | None = None,
        cover_image_url: str | None = None,
        status: CourseStatus = CourseStatus.DRAFT,
        difficulty_level: DifficultyLevelStatus | None = None,
        estimated_minutes: int | None = None,
        category: str | None = None,
        language_code: str | None = None,
        is_public: bool = False,
        published_at: datetime | None = None,
    ) -> Course:
        """Used by course-creation services to persist a new course record."""
        course = Course(
            educator_id=educator_id,
            title=title,
            subtitle=subtitle,
            description=description,
            cover_image_url=cover_image_url,
            status=status,
            difficulty_level=difficulty_level,
            estimated_minutes=estimated_minutes,
            category=category,
            language_code=language_code,
            is_public=is_public,
            published_at=published_at,
        )
        self.session.add(course)
        self.session.flush()
        return course

    def update(
        self,
        course: Course,
        *,
        title: str | None | object = _UNSET,
        subtitle: str | None | object = _UNSET,
        description: str | None | object = _UNSET,
        cover_image_url: str | None | object = _UNSET,
        difficulty_level: DifficultyLevelStatus | None | object = _UNSET,
        estimated_minutes: int | None | object = _UNSET,
        category: str | None | object = _UNSET,
        language_code: str | None | object = _UNSET,
        is_public: bool | object = _UNSET,
        published_at: datetime | None | object = _UNSET,
    ) -> Course:
        """Used by course-editing services to apply partial updates to a course."""
        if title is not _UNSET:
            course.title = title
        if subtitle is not _UNSET:
            course.subtitle = subtitle
        if description is not _UNSET:
            course.description = description
        if cover_image_url is not _UNSET:
            course.cover_image_url = cover_image_url
        if difficulty_level is not _UNSET:
            course.difficulty_level = difficulty_level
        if estimated_minutes is not _UNSET:
            course.estimated_minutes = estimated_minutes
        if category is not _UNSET:
            course.category = category
        if language_code is not _UNSET:
            course.language_code = language_code
        if is_public is not _UNSET:
            course.is_public = is_public
        if published_at is not _UNSET:
            course.published_at = published_at
        self.session.flush()
        return course

    def update_status(
        self,
        course: Course,
        *,
        status: CourseStatus,
        is_public: bool | object = _UNSET,
        published_at: datetime | None | object = _UNSET,
    ) -> Course:
        """Used by publishing services to change course status and publication metadata."""
        course.status = status
        if is_public is not _UNSET:
            course.is_public = is_public
        if published_at is not _UNSET:
            course.published_at = published_at
        self.session.flush()
        return course

    def touch(self, course: Course) -> Course:
        """Refreshes course.updated_at when related course content changes in other tables."""
        course.updated_at = now_local()
        self.session.flush()
        return course

    def delete(self, course: Course) -> None:
        """Used by course-management services to remove a course record."""
        self.session.delete(course)
        self.session.flush()
