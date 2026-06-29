from platform_common.errors.base import AppServiceError
from platform_common.errors.api import (
    forum_comment_not_found_error,
    forum_comment_write_forbidden_error,
    forum_post_pin_forbidden_error,
    forum_post_not_found_error,
    forum_post_write_forbidden_error,
    http_error,
    notification_not_found_error,
    notification_recipient_not_found_error,
    insufficient_permissions_error,
    invalid_credentials_error,
    invalid_identity_response_error,
    invalid_request_error,
    identity_service_unavailable_error,
)

__all__ = [
    "AppServiceError",
    "forum_comment_not_found_error",
    "forum_comment_write_forbidden_error",
    "forum_post_pin_forbidden_error",
    "forum_post_not_found_error",
    "forum_post_write_forbidden_error",
    "http_error",
    "identity_service_unavailable_error",
    "insufficient_permissions_error",
    "invalid_credentials_error",
    "invalid_identity_response_error",
    "invalid_request_error",
    "notification_not_found_error",
    "notification_recipient_not_found_error",
]
