from platform_common.errors import invalid_credentials_error


def parse_bearer_token(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise invalid_credentials_error()

    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise invalid_credentials_error()

    return token
