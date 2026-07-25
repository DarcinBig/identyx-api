"""
Email service business logic.

Responsibilities:
    - Build HTML content from Jinja2 templates
    - Build URLs for action links
    - Delegate sending to the SMTP provider
"""
import os
from datetime import datetime

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.core.config import get_settings
from app.providers.smtp import send_email
from app.schemas.email import (
    EmailSentResponse,
    SendResetPasswordEmailRequest,
    SendSecurityAlertEmailRequest,
    SendVerificationEmailRequest,
)

settings = get_settings()

# Absolute path to the templates folder
_TEMPLATES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    'templates'
)

# Jinja2 Environment — loaded only once
_jinja_env = Environment(
    loader=FileSystemLoader(_TEMPLATES_DIR),
    autoescape=select_autoescape(['html'])
)

class EmailService:
    async def send_verification_email(self, data: SendVerificationEmailRequest) -> EmailSentResponse:
        """
        Sends the account verification email.

        Link URL:
            {app_base_url}/auth/verify-email?token={verification_token}

        This route doesn't exist yet — it will be implemented
        in a future version with the verification logic.
        For now, the link is generated, but the route returns a 404 error.
        TODO Implement the verification logic.
        """
        verification_url = (
            f"{settings.app_base_url}/auth/verify-email"
            f"?token={data.verification_token}"
        )

        # Render HTML template
        template = _jinja_env.get_template("verify_email.html")
        html_content = template.render(
            username=data.username,
            verification_url=verification_url,
            year=datetime.now().year,
        )

        # Fallback raw text
        text_content = (
            f"Hi {data.username},\n\n"
            f"Please verify your email address by visiting:\n"
            f"{verification_url}\n\n"
            f"This link expires in 24 hours.\n\n"
            f"— The Identyx team"
        )

        sent = await send_email(
            to_email=data.email,
            subject="Verify your email — Identyx",
            html_content=html_content,
            text_content=text_content,
        )

        return EmailSentResponse(
            message="Verification email sent." if sent else "Failed to send verification email.",
            email=data.email,
            sent=sent,
        )

    async def send_reset_password_email(self, data: SendResetPasswordEmailRequest) -> EmailSentResponse:
        """
        Send the password reset email.

        Link URL:
            {app_base_url}/auth/reset-password?token={reset_token}
        """
        reset_url = (
            f"{settings.app_base_url}/auth/reset-password"
            f"?token={data.reset_token}"
        )

        template = _jinja_env.get_template("reset_password.html")
        html_content = template.render(
            username=data.username,
            reset_url=reset_url,
            year=datetime.now().year,
        )

        text_content = (
            f"Hi {data.username},\n\n"
            f"Reset your password by visiting:\n"
            f"{reset_url}\n\n"
            f"This link expires in 1 hour.\n"
            f"If you did not request this, ignore this email.\n\n"
            f"— The Identyx team"
        )

        sent = await send_email(
            to_email=data.email,
            subject="Reset your password — Identyx",
            html_content=html_content,
            text_content=text_content,
        )

        return EmailSentResponse(
            message="Reset password email sent." if sent else "Failed to send reset password email.",
            email=data.email,
            sent=sent,
        )

    async def send_security_alert_email(
        self, data: SendSecurityAlertEmailRequest
    ) -> EmailSentResponse:
        """
        Sends a security alert email.
        Triggered after a successful login following multiple failed attempts.
        """
        reset_url = (
            f"{settings.app_base_url}/auth/reset-password"
            f"?token={data.reset_token}"
        )

        template = _jinja_env.get_template("security_alert.html")
        html_content = template.render(
            username=data.username,
            failed_attempts=data.failed_attempts,
            reset_url=reset_url,
            year=datetime.now().year,
        )

        text_content = (
            f"Hi {data.username},\n\n"
            f"Your account was accessed after {data.failed_attempts} "
            f"failed login attempt(s).\n\n"
            f"If this was not you, change your password immediately:\n"
            f"{reset_url}\n\n"
            f"This link expires in 1 hour.\n\n"
            f"— The Identyx team"
        )

        sent = await send_email(
            to_email=data.email,
            subject="Security alert — Unusual login activity on your Identyx account",
            html_content=html_content,
            text_content=text_content,
        )

        return EmailSentResponse(
            message="Security alert email sent." if sent else "Failed to send security alert.",
            email=data.email,
            sent=sent,
        )