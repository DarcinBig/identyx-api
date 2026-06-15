
"""
Event handlers for events received by the email service.

Each handler corresponds to a Redis Pub/Sub channel.
The handler receives the raw JSON message and calls the email service.
"""
from app.events.types import UserRegisteredEvent
from app.services.email_service import EmailService
from app.schemas.email import SendVerificationEmailRequest

# # Shared instance — no state, no database
_email_service = EmailService()

async def handler_user_registered(data: str) -> None:
    """
    Handler for user.registered.
    Received after each successful registration from auth-service.
    Sends the verification email.
    """
    try:
        event = UserRegisteredEvent.from_json(data)
        print(
            f"[handler] user.registered received — "
            f"user_id: {event.user_id}, email: {event.email}"
        )

        await _email_service.send_verification_email(
            SendVerificationEmailRequest(
                email=event.email,
                username=event.username,
                verification_token=event.verification_token,
            )
        )

    except Exception as exc:
        print(f"[handler] handle_user_registered error: {exc}")