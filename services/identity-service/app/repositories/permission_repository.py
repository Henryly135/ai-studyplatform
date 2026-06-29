from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.permission import Permission
from app.models.role_permission import RolePermission


class PermissionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, permission_id: int) -> Permission | None:
        """Used by authorization services to load a permission by primary key."""
        return self.session.get(Permission, permission_id)

    def get_by_code(self, permission_code: str) -> Permission | None:
        """Used by authorization services to resolve a permission code."""
        stmt = select(Permission).where(Permission.permission_code == permission_code)
        return self.session.scalar(stmt)

    def list_all(self) -> list[Permission]:
        """Used by admin services to view all configured permissions."""
        stmt = select(Permission).order_by(Permission.permission_id)
        return list(self.session.scalars(stmt))

    def list_by_role(self, role_id: int) -> list[Permission]:
        """Used by authorization services to assemble the effective permissions for a role."""
        stmt = (
            select(Permission)
            .join(RolePermission, RolePermission.permission_id == Permission.permission_id)
            .where(RolePermission.role_id == role_id)
            .order_by(Permission.permission_id)
        )
        return list(self.session.scalars(stmt))
