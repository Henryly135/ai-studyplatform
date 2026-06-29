from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.learning_paths import LearningPath

_UNSET = object()


class LearningPathRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, learning_path_id: int) -> LearningPath | None:
        """Used by learning-path detail services to load a learning path by primary key."""
        return self.session.get(LearningPath, learning_path_id)

    def get_by_course_id(self, course_id: int) -> LearningPath | None:
        """Used by course-detail services to resolve the learning path attached to a course."""
        stmt = select(LearningPath).where(LearningPath.course_id == course_id)
        return self.session.scalar(stmt)

    def list_all(self) -> list[LearningPath]:
        """Used by admin services to view all learning paths."""
        stmt = select(LearningPath).order_by(LearningPath.learning_path_id)
        return list(self.session.scalars(stmt))

    def create(
        self,
        *,
        course_id: int,
        title: str,
        description: str | None = None,
    ) -> LearningPath:
        """Used by course-setup services to create a learning path for a course."""
        learning_path = LearningPath(
            course_id=course_id,
            title=title,
            description=description,
        )
        self.session.add(learning_path)
        self.session.flush()
        return learning_path

    def update(
        self,
        learning_path: LearningPath,
        *,
        title: str | object = _UNSET,
        description: str | None | object = _UNSET,
    ) -> LearningPath:
        """Used by learning-path management services to update path metadata."""
        if title is not _UNSET:
            learning_path.title = title
        if description is not _UNSET:
            learning_path.description = description
        self.session.flush()
        return learning_path

    def delete(self, learning_path: LearningPath) -> None:
        """Used by course-management services to remove a learning path record."""
        self.session.delete(learning_path)
        self.session.flush()
