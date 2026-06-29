from fastapi import HTTPException


def http_error(*, status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "message": message})


def invalid_credentials_error(message: str = "Invalid credentials") -> HTTPException:
    return http_error(status_code=401, code="INVALID_CREDENTIALS", message=message)


def identity_service_unavailable_error() -> HTTPException:
    return http_error(
        status_code=503,
        code="IDENTITY_SERVICE_UNAVAILABLE",
        message="Identity service unavailable",
    )


def invalid_identity_response_error() -> HTTPException:
    return http_error(
        status_code=502,
        code="INVALID_IDENTITY_RESPONSE",
        message="Invalid identity service response",
    )


def insufficient_permissions_error(message: str = "Insufficient permissions") -> HTTPException:
    return http_error(status_code=403, code="INSUFFICIENT_PERMISSIONS", message=message)


def invalid_request_error(message: str = "Invalid request") -> HTTPException:
    return http_error(status_code=400, code="INVALID_REQUEST", message=message)


def forum_post_not_found_error() -> HTTPException:
    return http_error(status_code=404, code="FORUM_POST_NOT_FOUND", message="Forum post not found")


def forum_comment_not_found_error() -> HTTPException:
    return http_error(status_code=404, code="FORUM_COMMENT_NOT_FOUND", message="Forum comment not found")


def forum_post_write_forbidden_error() -> HTTPException:
    return http_error(
        status_code=403,
        code="FORUM_POST_WRITE_FORBIDDEN",
        message="You can only modify your own forum posts",
    )


def forum_post_pin_forbidden_error() -> HTTPException:
    return http_error(
        status_code=403,
        code="FORUM_POST_PIN_FORBIDDEN",
        message="You do not have permission to pin forum posts for this course",
    )


def forum_comment_write_forbidden_error() -> HTTPException:
    return http_error(
        status_code=403,
        code="FORUM_COMMENT_WRITE_FORBIDDEN",
        message="You can only modify your own forum comments",
    )


def notification_not_found_error() -> HTTPException:
    return http_error(status_code=404, code="NOTIFICATION_NOT_FOUND", message="Notification not found")


def notification_recipient_not_found_error() -> HTTPException:
    return http_error(
        status_code=404,
        code="NOTIFICATION_RECIPIENT_NOT_FOUND",
        message="Notification recipient not found",
    )
