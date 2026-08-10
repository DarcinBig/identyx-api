from pydantic import BaseModel, EmailStr

# --- Requests ------------------------------------------------

class SendVerificationEmailRequest(BaseModel):
    """
    Triggers the sending of the verification email.
    Called by the auth-service after registering (fire and forget).
    """
    email: EmailStr
    username: str
    verification_token: str  # opaque token for the verification link

class SendResetPasswordEmailRequest(BaseModel):
    """
    Triggers the sending of the password reset email.
    Called by the auth-service when the user requests a reset.
    """
    email: EmailStr
    username: str
    reset_token: str    # opaque token for the reset link

class SendSecurityAlertEmailRequest(BaseModel):
    """
    Triggers the sending of a security alert email.
    Called after a successful login following multiple failed attempts.
    Warns the user and provides a direct link to change password.
    """
    email: EmailStr
    username: str
    failed_attempts: int
    reset_token: str

class SendNewLoginEmailRequest(BaseModel):
    """
    Triggers the sending of a new-login notification email.
    Sent after every successful login to alert the user
    of a new device connecting to their account (multi-device).
    """
    email: EmailStr
    username: str
    device_info: str   # User-Agent | IP
    client_ip: str
    login_time: str
    location: str      # "Paris, France" — resolved from client_ip

class SendAccountDeletionEmailRequest(BaseModel):
    """
    Triggers the sending of a GDPR account deletion confirmation email.
    Sent when the account owner requests a deletion.
    The deletion only happens once the one-time link is confirmed.
    """
    email: EmailStr
    username: str
    deletion_token: str   # opaque token for the deletion confirmation link

class SendEmailChangeEmailRequest(BaseModel):
    """
    Triggers the sending of an email change confirmation email.
    Sent to the NEW address when the owner requests an email change.
    The change only happens once the one-time link is confirmed.
    """
    email: EmailStr
    username: str
    email_change_token: str   # opaque token for the email change link

# --- Responses -----------------------------------------------

class EmailSentResponse(BaseModel):
    """Sending confirmation"""
    message: str
    email: str
    sent: bool

