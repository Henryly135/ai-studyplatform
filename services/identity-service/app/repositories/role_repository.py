from collections import defaultdict

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.role import Role
from app.models.user_role import UserRole


class RoleRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, role_id: int) -> Role | None:
        """Used by role and admin services to load a role by primary key."""
        return self.session.get(Role, role_id)

    def get_by_code(self, role_code: str) -> Role | None:
        """Used by registration and authorization services to resolve a role code."""
        stmt = select(Role).where(Role.role_code == role_code)
        return self.session.scalar(stmt)

    def list_all(self) -> list[Role]:
        """Used by admin services to display the available system roles."""
        stmt = select(Role).order_by(Role.role_id)
        return list(self.session.scalars(stmt))

    def assign_role(self, user_id: int, role_id: int) -> UserRole:
        """Used by registration, approval, and admin services to attach a role to a user."""
        user_role = UserRole(user_id=user_id, role_id=role_id)
        self.session.add(user_role)
        self.session.flush()
        return user_role

    def list_user_roles(self, user_id: int) -> list[Role]:
        """Used by authorization services to determine which roles a user currently has."""
        stmt = (
            select(Role)
            .join(UserRole, UserRole.role_id == Role.role_id)
            .where(UserRole.user_id == user_id)
            .order_by(Role.role_id)
        )
        return list(self.session.scalars(stmt))

    def list_roles_by_user_ids(self, user_ids: list[int]) -> dict[int, list[Role]]:
        """Used by internal directory services to resolve role sets for a batch of users."""
        if not user_ids:
            return {}

        stmt = (
            select(UserRole.user_id, Role)
            .join(Role, Role.role_id == UserRole.role_id)
            .where(UserRole.user_id.in_(user_ids))
            .order_by(UserRole.user_id, Role.role_id)
        )

        roles_by_user_id: dict[int, list[Role]] = defaultdict(list)
        for user_id, role in self.session.execute(stmt):
            roles_by_user_id[int(user_id)].append(role)

        return dict(roles_by_user_id)

    def list_user_ids_by_role_code(self, role_code: str) -> list[int]:
        stmt = (
            select(UserRole.user_id)
            .join(Role, Role.role_id == UserRole.role_id)
            .where(Role.role_code == role_code)
            .order_by(UserRole.user_id)
        )
        return [int(user_id) for user_id in self.session.scalars(stmt)]

    def clear_user_roles(self, user_id: int) -> None:
        """Used by admin services to replace a user's assigned roles."""
        stmt = delete(UserRole).where(UserRole.user_id == user_id)
        self.session.execute(stmt)
