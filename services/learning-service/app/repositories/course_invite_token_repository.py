from datetime import datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.course_invite_token import CourseInviteToken


def _now_utc():
    from datetime import timezone
    return datetime.now(timezone.utc).replace(tzinfo=None)


class CourseInviteTokenRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self,
        *,
        course_id: int,
        created_by: int,
        expires_at: datetime | None = None,
    ) -> CourseInviteToken:
        token = CourseInviteToken(
            invite_uuid=str(uuid4()),
            course_id=course_id,
            created_by=created_by,
            is_active=True,
            expires_at=expires_at,
        )
        self.session.add(token)
        self.session.flush()
        return token

    def get_valid_by_uuid(self, invite_uuid: str) -> CourseInviteToken | None:
        now = _now_utc()
        stmt = select(CourseInviteToken).where(
            CourseInviteToken.invite_uuid == invite_uuid,
            CourseInviteToken.is_active.is_(True),
        )
        token = self.session.scalar(stmt)
        if token is None:
            return None
        if token.expires_at is not None and token.expires_at < now:
            return None
        return token

    def get_by_uuid(self, invite_uuid: str) -> CourseInviteToken | None:
        stmt = select(CourseInviteToken).where(CourseInviteToken.invite_uuid == invite_uuid)
        return self.session.scalar(stmt)

    def list_by_course(self, course_id: int) -> list[CourseInviteToken]:
        stmt = (
            select(CourseInviteToken)
            .where(CourseInviteToken.course_id == course_id)
            .order_by(CourseInviteToken.created_at.desc())
        )
        return list(self.session.scalars(stmt))

    def deactivate(self, token: CourseInviteToken) -> None:
        token.is_active = False
        self.session.flush()
