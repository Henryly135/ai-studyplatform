from datetime import datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.time import now_local
from app.models.educator_invite_token import EducatorInviteToken


class EducatorInviteTokenRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self,
        *,
        created_by_user_id: int,
        token_hash: str,
        expires_at: datetime,
    ) -> EducatorInviteToken:
        token = EducatorInviteToken(
            invite_uuid=str(uuid4()),
            token_hash=token_hash,
            created_by_user_id=created_by_user_id,
            expires_at=expires_at,
        )
        self.session.add(token)
        self.session.flush()
        return token

    def get_valid_by_token_hash(self, token_hash: str) -> EducatorInviteToken | None:
        stmt = select(EducatorInviteToken).where(
            EducatorInviteToken.token_hash == token_hash,
            EducatorInviteToken.used_at.is_(None),
            EducatorInviteToken.expires_at > now_local(),
        )
        return self.session.scalar(stmt)

    def get_by_uuid(self, invite_uuid: str) -> EducatorInviteToken | None:
        stmt = select(EducatorInviteToken).where(
            EducatorInviteToken.invite_uuid == invite_uuid,
        )
        return self.session.scalar(stmt)

    def mark_used(self, token: EducatorInviteToken, used_by_user_id: int) -> None:
        token.used_at = now_local()
        token.used_by_user_id = used_by_user_id
        self.session.flush()

    def list_by_creator(self, created_by_user_id: int) -> list[EducatorInviteToken]:
        stmt = (
            select(EducatorInviteToken)
            .where(EducatorInviteToken.created_by_user_id == created_by_user_id)
            .order_by(EducatorInviteToken.created_at.desc())
        )
        return list(self.session.scalars(stmt))
