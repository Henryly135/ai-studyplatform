from sqlalchemy.orm import Session

from app.core.uuid_codec import encode_user_uuid
from app.repositories.role_repository import RoleRepository
from app.repositories.user_repository import UserRepository
from app.schemas.user_directory import UserDirectoryLookupResponse, UserDirectoryRead
from app.services.auth_service import role_code_to_identity


class UserDirectoryService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.roles = RoleRepository(session)

    def lookup_users_by_ids(self, *, user_ids: list[int]) -> UserDirectoryLookupResponse:
        deduplicated_user_ids: list[int] = []
        seen_user_ids: set[int] = set()
        for user_id in user_ids:
            if user_id not in seen_user_ids:
                seen_user_ids.add(user_id)
                deduplicated_user_ids.append(user_id)

        user_rows = self.users.list_by_ids(deduplicated_user_ids)
        user_map = {user.user_id: user for user in user_rows}
        roles_by_user_id = self.roles.list_roles_by_user_ids(deduplicated_user_ids)

        response_items: list[UserDirectoryRead] = []
        for user_id in deduplicated_user_ids:
            user = user_map.get(user_id)
            if user is None:
                continue

            roles = roles_by_user_id.get(user.user_id, [])
            role_codes = [role.role_code for role in roles]
            primary_role_code = role_codes[0] if role_codes else None
            response_items.append(
                UserDirectoryRead(
                    id=user.user_id,
                    userUuid=encode_user_uuid(user.user_id),
                    email=user.email,
                    userName=user.full_name,
                    identity=role_code_to_identity(primary_role_code),
                    roleCodes=role_codes,
                    emailVerified=bool(user.email_verified),
                    accountStatus=user.account_status.value
                    if hasattr(user.account_status, "value")
                    else str(user.account_status),
                )
            )

        return UserDirectoryLookupResponse(users=response_items)
