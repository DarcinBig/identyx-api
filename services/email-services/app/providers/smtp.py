"""
Asynchronous SMTP provider with aiosmtplib.

Single responsibility:
    - Establish an SMTP connection
    - Send an email (HTML + text fallback)
    - Close the connection properly

Compatible with:
    - Brevo (development)
    - SendGrid, Resend, Mailgun (production) via SMTP relay
    - Gmail SMTP (personal testing)
"""
import aiosmtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger("uvicorn.error")

async def send_email(
        to_email: str,
        subject: str,
        html_content: str,
        text_content: str | None = None,
) -> bool:
    """
    Sends an email via SMTP asynchronously.

    Args:
        to_email: recipient's email address
        subject: email subject
        html_content: HTML content of the email
        text_content: fallback plain text (optional)

    Returns:
        True if sent successfully, False otherwise.

    Never throws an exception — sending failure
    should not block the main flow (register, etc.).
    """
    try:
        # Construct the MIME message
        message = MIMEMultipart("alternative")
        message["From"] = f"{settings.emails_from_name} <{settings.emails_from}>"
        message["To"] = to_email
        message["Subject"] = subject

        # Fallback raw text
        if text_content:
            message.attach(MIMEText(text_content, "plain", "utf-8"))

        # Main HTML content
        message.attach(MIMEText(html_content, "html", "utf-8"))

        # Send via aiosmtplib
        await aiosmtplib.send(
            message,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_user,
            password=settings.smtp_password,
            start_tls=settings.smtp_use_tls
        )

        logger.info(f"[smtp] Sent email to {to_email} — subject: {subject}")
        return True

    except Exception as exc:
        logger.info(f"[smtp] Email sending error to {to_email}: {type(exc).__name__}: {exc}")
        return False
