from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.time import now_local
from app.models.tokens import EmailVerificationToken, PasswordResetToken


class TokenRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_email_verification_token(
        self,
        *,
        user_id: int,
        token_hash: str,
        expires_at: datetime,
    ) -> EmailVerificationToken:
        """Used by registration and resend-verification services to issue an email verification token."""
        token = EmailVerificationToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        self.session.add(token)
        self.session.flush()
        return token

    def get_valid_email_verification_token(self, token_hash: str) -> EmailVerificationToken | None:
        """Used by email verification services to load a still-valid verification token."""
        stmt = select(EmailVerificationToken).where(
            EmailVerificationToken.token_hash == token_hash,
            EmailVerificationToken.used_at.is_(None),
            EmailVerificationToken.expires_at > now_local(),
        )
        return self.session.scalar(stmt)

    def create_password_reset_token(
        self,
        *,
        user_id: int,
        token_hash: str,
        expires_at: datetime,
    ) -> PasswordResetToken:
        """Used by forgot-password services to issue a password reset token."""
        token = PasswordResetToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        self.session.add(token)
        self.session.flush()
        return token

    def get_valid_password_reset_token(self, token_hash: str) -> PasswordResetToken | None:
        """Used by password reset services to load a still-valid reset token."""
        stmt = select(PasswordResetToken).where(
            PasswordResetToken.token_hash == token_hash,
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.expires_at > now_local(),
        )
        return self.session.scalar(stmt)

    def invalidate_token(
        self,
        *,
        email_verification_token: EmailVerificationToken | None = None,
        password_reset_token: PasswordResetToken | None = None,
        used_at: datetime | None = None,
    ) -> None:
        """Used by verification and reset services to mark token records as consumed."""
        timestamp = used_at or now_local()
        if email_verification_token is not None:
            email_verification_token.used_at = timestamp
        if password_reset_token is not None:
            password_reset_token.used_at = timestamp
        self.session.flush()

    def invalidate_user_tokens(self, user_id: int) -> None:
        """Used by security services to expire all active tokens belonging to a user."""
        timestamp = now_local()
        for model in (EmailVerificationToken, PasswordResetToken):
            stmt = select(model).where(
                model.user_id == user_id,
                model.used_at.is_(None),
                model.expires_at > timestamp,
            )
            for token in self.session.scalars(stmt):
                token.used_at = timestamp
        self.session.flush()
