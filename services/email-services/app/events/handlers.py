"""
Event handlers for email-service.
Consumes Kafka topics and sends the corresponding emails.
"""

import logging
import secrets

from app.events.types import AuthSuspiciousLoginEvent, UserRegisteredEvent
from app.schemas.email import (
    SendSecurityAlertEmailRequest,
    SendVerificationEmailRequest,
)
from app.services.email_service import EmailService

logger = logging.getLogger("email-service.handlers")

_email_service = EmailService()


async def handler_user_registered(data: str) -> None:
    """
    Handler for user.registered.
    Sends the verification email.
    """
    try:
        event = UserRegisteredEvent.from_json(data)
        logger.info("handler_user_registered", extra={
            "user_id": event.user_id,
            "email": event.email,
        })
        await _email_service.send_verification_email(
            SendVerificationEmailRequest(
                email=event.email,
                username=event.username,
                verification_token=event.verification_token,
            )
        )
    except Exception as exc:
        logger.error("handler_user_registered_error", extra={"error": str(exc)})


async def handler_auth_suspicious(data: str) -> None:
    """
    Handler for auth.suspicious.
    Sends a security alert email after a suspicious login.
    TODO reset_token is temporary — will be replaced by HMAC-signed token.
    """
    try:
        event = AuthSuspiciousLoginEvent.from_json(data)
        logger.info("handler_auth_suspicious", extra={
            "user_id": event.user_id,
            "email": event.email,
            "failed_attempts": event.failed_attempts,
        })

        # TODO Temporary token — will be replaced by HMAC-signed token
        reset_token = secrets.token_urlsafe(32)

        await _email_service.send_security_alert_email(
            SendSecurityAlertEmailRequest(
                email=event.email,
                username=event.username,
                failed_attempts=event.failed_attempts,
                reset_token=reset_token,
            )
        )
    except Exception as exc:
        logger.error("handler_auth_suspicious_error", extra={"error": str(exc)})
