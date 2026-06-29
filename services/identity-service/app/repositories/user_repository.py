from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.time import now_local
from app.models.user import AccountStatus, User


class UserRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, user_id: int) -> User | None:
        """Used by user/profile services to load a user by primary key."""
        return self.session.get(User, user_id)

    def get_by_email(self, email: str) -> User | None:
        """Used by registration and login services to locate a user by unique email."""
        stmt = select(User).where(User.email == email)
        return self.session.scalar(stmt)

    def list_all(self) -> list[User]:
        """Used by admin user-management services to review all user accounts."""
        stmt = select(User).order_by(User.user_id)
        return list(self.session.scalars(stmt))

    def list_by_ids(self, user_ids: list[int]) -> list[User]:
        """Used by internal directory services to resolve a batch of users by primary key."""
        if not user_ids:
            return []

        stmt = select(User).where(User.user_id.in_(user_ids)).order_by(User.user_id)
        return list(self.session.scalars(stmt))

    def create(
        self,
        *,
        email: str,
        password_hash: str,
        full_name: str,
        account_status: AccountStatus = AccountStatus.PENDING,
        email_verified: bool = False,
    ) -> User:
        """Used by registration services to create a new user account record."""
        user = User(
            email=email,
            password_hash=password_hash,
            full_name=full_name,
            account_status=account_status,
            email_verified=email_verified,
        )
        self.session.add(user)
        self.session.flush()
        return user

    def update_last_login(self, user: User, login_time: datetime | None = None) -> User:
        """Used by login services after successful authentication to store the last login time."""
        user.last_login_at = login_time or now_local()
        self.session.flush()
        return user

    def mark_email_verified(self, user: User) -> User:
        """Used by email verification (Admin) services when a verification token is confirmed."""
        user.email_verified = True
        self.session.flush()
        return user

    def update_account_status(self, user: User, account_status: AccountStatus) -> User:
        """Used by approval and admin user-management services to change account status."""
        user.account_status = account_status
        self.session.flush()
        return user

    def update_password(self, user: User, password_hash: str) -> User:
        """Used by password reset and change-password services to update user's password hash."""
        user.password_hash = password_hash
        self.session.flush()
        return user
