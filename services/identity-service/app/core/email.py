import os
import smtplib
from email.message import EmailMessage
from urllib.parse import urlencode

from app.core.config import settings


def _default_public_base_url() -> str:
    explicit = os.getenv("PUBLIC_BASE_URL")
    if explicit:
        return explicit.rstrip("/")

    nginx_port = os.getenv("NGINX_PORT")
    identity_port = os.getenv("IDENTITY_PORT")

    if nginx_port:
        return f"http://localhost:{nginx_port}/api"

    if identity_port:
        return f"http://localhost:{identity_port}"

    vite_api_base = os.getenv("VITE_API_BASE_URL")
    if vite_api_base:
        return vite_api_base.rstrip("/")

    return "http://localhost:8000"


def build_verify_link(token: str, frontend_base_url: str | None = None) -> str:
    if frontend_base_url:
        base = frontend_base_url.rstrip("/")
    else:
        explicit = os.getenv("PUBLIC_FRONTEND_URL")
        public_base = os.getenv("PUBLIC_BASE_URL", "")
        if explicit:
            base = explicit.rstrip("/")
        elif public_base:
            if public_base.endswith("/api"):
                base = public_base[:-4]
            else:
                base = public_base.rstrip("/")
        else:
            nginx_port = os.getenv("NGINX_PORT")
            base = f"http://localhost:{nginx_port}" if nginx_port else "http://localhost:5173"

    verify_path = "/verify-email"
    qs = urlencode({"token": token})
    return f"{base}{verify_path}?{qs}"


def send_verification_link(email: str, token: str, frontend_base_url: str | None = None) -> None:
    link = build_verify_link(token, frontend_base_url=frontend_base_url)
    print(f"[verify-link] to={email} link={link}")

    smtp_host = os.getenv("SMTP_HOST")
    if not smtp_host:
        return

    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASS")
    smtp_from = os.getenv("SMTP_FROM", smtp_user or "no-reply@example.com")
    use_tls = os.getenv("SMTP_TLS", "true").lower() not in ("0", "false", "no")

    msg = EmailMessage()
    msg["Subject"] = "Verify your email"
    msg["From"] = smtp_from
    msg["To"] = email
    msg.set_content(
        "Please verify your email by clicking the link below:\n\n"
        f"{link}\n\n"
        "If you did not create an account, you can ignore this email.\n"
    )

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
            server.ehlo()
            if use_tls:
                server.starttls()
                server.ehlo()
            if smtp_user and smtp_pass:
                server.login(smtp_user, smtp_pass)
            server.send_message(msg)
    except Exception as e:
        print(f"[email-error] failed to send verification email to={email}: {e}")


def build_reset_link(token: str, frontend_base_url: str | None = None) -> str:
    if frontend_base_url:
        base = frontend_base_url.rstrip("/")
    else:
        explicit = os.getenv("PUBLIC_FRONTEND_URL")
        public_base = os.getenv("PUBLIC_BASE_URL", "")
        if explicit:
            base = explicit.rstrip("/")
        elif public_base:
            if public_base.endswith("/api"):
                base = public_base[:-4]
            else:
                base = public_base.rstrip("/")
        else:
            nginx_port = os.getenv("NGINX_PORT")
            base = f"http://localhost:{nginx_port}" if nginx_port else "http://localhost:5173"

    reset_path = "/reset-password"
    qs = urlencode({"token": token})
    return f"{base}{reset_path}?{qs}"


def send_password_reset_link(email: str, token: str, frontend_base_url: str | None = None) -> None:
    link = build_reset_link(token, frontend_base_url=frontend_base_url)
    print(f"[reset-link] to={email} link={link}")

    smtp_host = os.getenv("SMTP_HOST")
    if not smtp_host:
        return

    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASS")
    smtp_from = os.getenv("SMTP_FROM", smtp_user or "no-reply@example.com")
    use_tls = os.getenv("SMTP_TLS", "true").lower() not in ("0", "false", "no")

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

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
            server.ehlo()
            if use_tls:
                server.starttls()
                server.ehlo()
            if smtp_user and smtp_pass:
                server.login(smtp_user, smtp_pass)
            server.send_message(msg)
    except Exception as e:
        print(f"[email-error] failed to send password reset email to={email}: {e}")


def send_educator_invite_email(email: str, invite_url: str) -> None:
    link = invite_url
    print(f"[educator-invite] to={email} link={link}")

    smtp_host = os.getenv("SMTP_HOST")
    if not smtp_host:
        return

    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASS")
    smtp_from = os.getenv("SMTP_FROM", smtp_user or "no-reply@example.com")
    use_tls = os.getenv("SMTP_TLS", "true").lower() not in ("0", "false", "no")

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

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
            server.ehlo()
            if use_tls:
                server.starttls()
                server.ehlo()
            if smtp_user and smtp_pass:
                server.login(smtp_user, smtp_pass)
            server.send_message(msg)
    except Exception as e:
        print(f"[email-error] failed to send educator invite email to={email}: {e}")


def send_educator_approval_result_email(
    email: str,
    user_name: str,
    result: str,
    review_comment: str | None = None,
) -> None:
    normalized_result = result.strip().lower()
    if normalized_result not in {"approved", "rejected"}:
        raise ValueError("result must be approved or rejected")

    print(f"[educator-approval-result] to={email} result={normalized_result}")

    smtp_host = os.getenv("SMTP_HOST")
    if not smtp_host:
        return

    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASS")
    smtp_from = os.getenv("SMTP_FROM", smtp_user or "no-reply@example.com")
    use_tls = os.getenv("SMTP_TLS", "true").lower() not in ("0", "false", "no")

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

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
            server.ehlo()
            if use_tls:
                server.starttls()
                server.ehlo()
            if smtp_user and smtp_pass:
                server.login(smtp_user, smtp_pass)
            server.send_message(msg)
    except Exception as e:
        print(f"[email-error] failed to send educator approval result email to={email}: {e}")
