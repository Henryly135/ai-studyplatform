from platform_common.errors import invalid_identity_response_error


def extract_permission_codes(permissions_payload: dict) -> set[str]:
    permissions = permissions_payload.get("permissions")
    if not isinstance(permissions, list):
        raise invalid_identity_response_error()

    return {
        permission.get("permissionCode")
        for permission in permissions
        if isinstance(permission, dict) and permission.get("permissionCode")
    }
