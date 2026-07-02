import hashlib
import hmac
import logging
import os
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from urllib.parse import urlencode

from app.core.config import settings
from app.core.public_url import PublicFrontendUrlNotConfiguredError, configured_public_frontend_base_url

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EmailDeliveryResult:
    attempted: bool
    delivered: bool
    reason: str | None = None


def _recipient_fingerprint(email: str) -> str:
    key = settings.jwt_secret_key.encode("utf-8", errors="ignore")
    value = email.strip().lower().encode("utf-8", errors="ignore")
    return hmac.new(key, value, hashlib.sha256).hexdigest()[:12]


def _smtp_from_address() -> str:
    return os.getenv("SMTP_FROM") or os.getenv("SMTP_USER") or "no-reply@example.com"


def _send_smtp_message(*, purpose: str, recipient_email: str, message: EmailMessage) -> EmailDeliveryResult:
    recipient_hash = _recipient_fingerprint(recipient_email)
    smtp_host = os.getenv("SMTP_HOST")
    if not smtp_host:
        logger.info(
            "Email delivery skipped purpose=%s recipient_hash=%s reason=smtp_not_configured",
            purpose,
            recipient_hash,
        )
        return EmailDeliveryResult(attempted=False, delivered=False, reason="smtp_not_configured")

    try:
        smtp_port = int(os.getenv("SMTP_PORT", "587"))
    except ValueError:
        logger.warning(
            "Email delivery skipped purpose=%s recipient_hash=%s reason=invalid_smtp_port",
            purpose,
            recipient_hash,
        )
        return EmailDeliveryResult(attempted=False, delivered=False, reason="invalid_smtp_port")

    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASS")
    use_tls = os.getenv("SMTP_TLS", "true").lower() not in ("0", "false", "no")

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
            server.ehlo()
            if use_tls:
                server.starttls()
                server.ehlo()
            if smtp_user and smtp_pass:
                server.login(smtp_user, smtp_pass)
            server.send_message(message)
    except Exception as exc:
        reason = f"smtp_error:{type(exc).__name__}"
        logger.warning(
            "Email delivery failed purpose=%s recipient_hash=%s reason=%s",
            purpose,
            recipient_hash,
            reason,
        )
        return EmailDeliveryResult(attempted=True, delivered=False, reason=reason)

    logger.info("Email delivered purpose=%s recipient_hash=%s", purpose, recipient_hash)
    return EmailDeliveryResult(attempted=True, delivered=True)


def _email_frontend_base_url(frontend_base_url: str | None = None) -> str:
    if frontend_base_url:
        return frontend_base_url.rstrip("/")

    configured = configured_public_frontend_base_url()
    if configured:
        return configured

    if os.getenv("APP_ENV", "").strip().lower() == "production":
        raise PublicFrontendUrlNotConfiguredError("Public frontend URL is not configured")

    nginx_port = os.getenv("NGINX_PORT")
    return f"http://localhost:{nginx_port}" if nginx_port else "http://localhost:5173"


def build_verify_link(token: str, frontend_base_url: str | None = None) -> str:
    base = _email_frontend_base_url(frontend_base_url)

    verify_path = "/verify-email"
    qs = urlencode({"token": token})
    return f"{base}{verify_path}?{qs}"


def send_verification_link(
    email: str, token: str, frontend_base_url: str | None = None
) -> EmailDeliveryResult:
    link = build_verify_link(token, frontend_base_url=frontend_base_url)
    smtp_from = _smtp_from_address()

    msg = EmailMessage()
    msg["Subject"] = "Verify your email"
    msg["From"] = smtp_from
    msg["To"] = email
    msg.set_content(
        "Please verify your email by clicking the link below:\n\n"
        f"{link}\n\n"
        "If you did not create an account, you can ignore this email.\n"
    )

    return _send_smtp_message(purpose="email_verification", recipient_email=email, message=msg)


def build_reset_link(token: str, frontend_base_url: str | None = None) -> str:
    base = _email_frontend_base_url(frontend_base_url)

    reset_path = "/reset-password"
    qs = urlencode({"token": token})
    return f"{base}{reset_path}?{qs}"


def send_password_reset_link(
    email: str, token: str, frontend_base_url: str | None = None
) -> EmailDeliveryResult:
    link = build_reset_link(token, frontend_base_url=frontend_base_url)
    smtp_from = _smtp_from_address()

    msg = EmailMessage()
    msg["Subject"] = "Reset your password"
    msg["From"] = smtp_from
    msg["To"] = email
    expiry_minutes = settings.password_reset_token_expire_minutes
    expiry_label = (
        "1 minute"
        if expiry_minutes == 1
        else f"{expiry_minutes} minutes"
    )
    msg.set_content(
        "You requested a password reset. Click the link below to set a new password:\n\n"
        f"{link}\n\n"
        f"This link expires in {expiry_label}.\n\n"
        "If you did not request a password reset, you can ignore this email.\n"
    )

    return _send_smtp_message(purpose="password_reset", recipient_email=email, message=msg)


def send_educator_invite_email(email: str, invite_url: str) -> EmailDeliveryResult:
    link = invite_url
    smtp_from = _smtp_from_address()

    msg = EmailMessage()
    msg["Subject"] = "You've been invited to join as an Educator"
    msg["From"] = smtp_from
    msg["To"] = email
    msg.set_content(
        "You have been invited to register as an Educator on our platform.\n\n"
        "Click the link below to set up your account:\n\n"
        f"{link}\n\n"
        "This link is one-time use and expires in 7 days.\n\n"
        "If you did not expect this invitation, you can ignore this email.\n"
    )

    return _send_smtp_message(purpose="educator_invite", recipient_email=email, message=msg)


def send_educator_approval_result_email(
    email: str,
    user_name: str,
    result: str,
    review_comment: str | None = None,
) -> EmailDeliveryResult:
    normalized_result = result.strip().lower()
    if normalized_result not in {"approved", "rejected"}:
        raise ValueError("result must be approved or rejected")

    smtp_from = _smtp_from_address()

    msg = EmailMessage()
    msg["Subject"] = (
        "Your educator account has been approved!"
        if normalized_result == "approved"
        else "Your educator account request was rejected!"
    )
    msg["From"] = smtp_from
    msg["To"] = email
    if normalized_result == "approved":
        body = (
            f"Hello {user_name},\n\n"
            "Your educator account request has been approved successfully.\n"
            "You can now sign in and start using educator features on the platform.\n\n"
            "If this was not expected, please contact the platform administrator.\n"
        )
    else:
        review_note = (
            f"\nReview comment: {review_comment}\n"
            if review_comment and review_comment.strip()
            else ""
        )
        body = (
            f"Hello {user_name},\n\n"
            "Your educator account request was rejected.\n"
            f"{review_note}\n"
            "If you need more information, please contact the platform administrator.\n"
        )
    msg.set_content(body)

    return _send_smtp_message(
        purpose=f"educator_approval_{normalized_result}",
        recipient_email=email,
        message=msg,
    )
