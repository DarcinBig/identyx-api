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
    SendAccountDeletionEmailRequest,
    SendEmailChangeEmailRequest,
    SendEmailChangedNotificationRequest,
    SendNewLoginEmailRequest,
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
            f"{settings.app_base_url}/v1/auth/verify-email"
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

    async def send_new_login_email(
        self, data: SendNewLoginEmailRequest
    ) -> EmailSentResponse:
        """
        Sends a new-login notification email.
        Sent after every successful login so the user can
        detect an unauthorized access from an unknown device.
        """
        secure_url = f"{settings.app_base_url}/v1/auth/reset-password"

        # Render HTML template
        template = _jinja_env.get_template("new_login.html")
        html_content = template.render(
            username=data.username,
            login_time=data.login_time,
            client_ip=data.client_ip,
            device_info=data.device_info,
            location=data.location,
            secure_url=secure_url,
            year=datetime.now().year,
        )

        # Fallback raw text
        text_content = (
            f"Hi {data.username},\n\n"
            f"A new login was detected on your account.\n\n"
            f"Date & Time: {data.login_time}\n"
            f"IP Address: {data.client_ip}\n"
            f"Location: {data.location}\n"
            f"Device: {data.device_info}\n\n"
            f"If this was not you, secure your account immediately:\n"
            f"{secure_url}\n\n"
            f"— The Identyx team"
        )

        sent = await send_email(
            to_email=data.email,
            subject="New login to your Identyx account",
            html_content=html_content,
            text_content=text_content,
        )

        return EmailSentResponse(
            message="New login email sent." if sent else "Failed to send new login email.",
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
            f"{settings.app_base_url}/v1/auth/reset-password"
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
            f"{settings.app_base_url}/v1/auth/reset-password"
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

    async def send_account_deletion_email(
        self, data: SendAccountDeletionEmailRequest
    ) -> EmailSentResponse:
        """
        Sends a GDPR account deletion confirmation email.
        Triggered when the owner requests a deletion.

        Link URL:
            {app_base_url}/auth/confirm-deletion?token={deletion_token}

        The account is only erased once the link is confirmed.
        The link is single-use and expires after 24 hours.
        """
        deletion_url = (
            f"{settings.app_base_url}/v1/auth/confirm-deletion"
            f"?token={data.deletion_token}"
        )

        template = _jinja_env.get_template("account_deletion.html")
        html_content = template.render(
            username=data.username,
            deletion_url=deletion_url,
            year=datetime.now().year,
        )

        text_content = (
            f"Hi {data.username},\n\n"
            f"We received a request to permanently delete your Identyx "
            f"account.\n\n"
            f"If this was you, confirm the deletion by visiting:\n"
            f"{deletion_url}\n\n"
            f"This action is irreversible and all your data will be "
            f"permanently erased.\n"
            f"This link expires in 24 hours.\n"
            f"If you did not request this, you can safely ignore this email.\n\n"
            f"— The Identyx team"
        )

        sent = await send_email(
            to_email=data.email,
            subject="Confirm your account deletion — Identyx",
            html_content=html_content,
            text_content=text_content,
        )

        return EmailSentResponse(
            message="Account deletion email sent." if sent else "Failed to send account deletion email.",
            email=data.email,
            sent=sent,
        )

    async def send_email_change_email(
        self, data: SendEmailChangeEmailRequest
    ) -> EmailSentResponse:
        """
        Sends an email change confirmation email.
        Sent to the NEW address when the owner requests a change.

        Link URL:
            {app_base_url}/auth/confirm-email-change?token={email_change_token}

        The email is only replaced once the link is confirmed.
        The link is single-use and expires after 24 hours.
        """
        email_change_url = (
            f"{settings.app_base_url}/v1/auth/confirm-email-change"
            f"?token={data.email_change_token}"
        )

        template = _jinja_env.get_template("email_change.html")
        html_content = template.render(
            username=data.username,
            email_change_url=email_change_url,
            year=datetime.now().year,
        )

        text_content = (
            f"Hi {data.username},\n\n"
            f"You asked to change the email address associated with your "
            f"Identyx account.\n\n"
            f"Confirm the change by visiting:\n"
            f"{email_change_url}\n\n"
            f"This link expires in 24 hours.\n"
            f"If you did not request this, you can safely ignore this email.\n\n"
            f"— The Identyx team"
        )

        sent = await send_email(
            to_email=data.email,
            subject="Confirm your new email address — Identyx",
            html_content=html_content,
            text_content=text_content,
        )

        return EmailSentResponse(
            message="Email change email sent." if sent else "Failed to send email change email.",
            email=data.email,
            sent=sent,
        )

    async def send_email_changed_notification(
        self, data: SendEmailChangedNotificationRequest
    ) -> EmailSentResponse:
        """
        Sends a notification that the email address was successfully changed.
        Sent to the NEW address after the email change is confirmed.
        """
        template = _jinja_env.get_template("email_changed.html")
        html_content = template.render(
            username=data.username,
            email=data.email,
            old_email=data.old_email,
            year=datetime.now().year,
        )

        text_content = (
            f"Hi {data.username},\n\n"
            f"Your email address has been successfully updated.\n\n"
            f"Previous email: {data.old_email}\n"
            f"New email: {data.email}\n\n"
            f"All future correspondence will be sent to your new address.\n"
            f"If you did not make this change, please contact our support team immediately.\n\n"
            f"— The Identyx team"
        )

        sent = await send_email(
            to_email=data.email,
            subject="Your email has been updated — Identyx",
            html_content=html_content,
            text_content=text_content,
        )

        return EmailSentResponse(
            message="Email changed notification sent." if sent else "Failed to send email changed notification.",
            email=data.email,
            sent=sent,
        )