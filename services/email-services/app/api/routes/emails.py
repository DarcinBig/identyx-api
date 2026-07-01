from fastapi import APIRouter, status

from app.schemas.email import (
    EmailSentResponse,
    SendResetPasswordEmailRequest,
    SendVerificationEmailRequest,
)
from app.services.email_service import EmailService

router = APIRouter(prefix="/emails", tags=["emails"])

# No database — stateless shared instance
_service = EmailService()

@router.post(
    "/verify",
    response_model=EmailSentResponse,
    status_code=status.HTTP_200_OK,
    summary="[Internal] Send verification email",
    operation_id="verify-email",
    include_in_schema=False,
)
async def send_verification_email(data: SendVerificationEmailRequest):
    """
    Sends the account verification email.
    Called by the auth-service after registration (fire and forget).
    Never returns an error—failure is silently logged.
    """
    return await _service.send_verification_email(data)

@router.post(
    "/reset-password",
    response_model=EmailSentResponse,
    status_code=status.HTTP_200_OK,
    summary="[Internal] Send reset password email",
    include_in_schema=False,
)
async def send_reset_password_email(data: SendResetPasswordEmailRequest):
    """
    Sends the password reset email.
    Called by auth-service when the user requests a reset.
    """
    return await _service.send_reset_password_email(data)