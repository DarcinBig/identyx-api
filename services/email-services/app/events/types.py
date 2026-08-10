import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime

# --- Kafka topics ---------------------------------------------

CHANNEL_USER_REGISTERED = "user.registered"
CHANNEL_USER_DELETED = "user.deleted"
CHANNEL_USER_DELETION_REQUESTED = "user.deletion_requested"
CHANNEL_USER_EMAIL_CHANGE_REQUESTED = "user.email_change_requested"
CHANNEL_AUTH_LOGIN = "auth.login"
CHANNEL_AUTH_SUSPICIOUS = "auth.suspicious"
CHANNEL_AUTH_NEW_LOGIN = "auth.new_login"


# --- Event payloads -------------------------------------------

@dataclass
class UserRegisteredEvent:
    """
    Published by the auth-service after successful registration.
    Consumed by the email-service to send the verification email.
    """
    user_id: str
    email: str
    username: str
    verification_token: str
    occurred_at: str = ""

    def __post_init__(self):
        if not self.occurred_at:
            self.occurred_at = datetime.now(UTC).isoformat()

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, data: str) ->  UserRegisteredEvent:
        return cls(**json.loads(data))

@dataclass
class UserDeletedEvent:
    """
    Published by auth-service if an account is deleted.
    """
    user_id: str
    email: str
    occurred_at: str = ""

    def __post_init__(self):
        if not self.occurred_at:
            self.occurred_at = datetime.now(UTC).isoformat()

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, data: str) -> UserDeletedEvent:
        return cls(**json.loads(data))

@dataclass
class UserDeletionRequestedEvent:
    """
    Published by auth-service when the owner requests a GDPR account
    deletion. Consumed by the email-service to send the confirmation
    email containing the deletion link.

    deletion_token: HMAC-signed one-time token used to build the
                    confirmation link in the email. Expires after 24h.
    """
    user_id: str
    email: str
    username: str
    deletion_token: str
    occurred_at: str = ""

    def __post_init__(self):
        if not self.occurred_at:
            self.occurred_at = datetime.now(UTC).isoformat()

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, data: str) -> UserDeletionRequestedEvent:
        return cls(**json.loads(data))

@dataclass
class UserEmailChangeRequestedEvent:
    """
    Published by auth-service when the owner asks to change their email
    address. Consumed by the email-service to send the confirmation
    email to the NEW address.

    email: the pending (new) email address.
    email_change_token: HMAC-signed one-time token used to build the
                        confirmation link in the email. Expires after 24h.
    """
    user_id: str
    email: str
    username: str
    email_change_token: str
    occurred_at: str = ""

    def __post_init__(self):
        if not self.occurred_at:
            self.occurred_at = datetime.now(UTC).isoformat()

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, data: str) -> UserEmailChangeRequestedEvent:
        return cls(**json.loads(data))

@dataclass
class AuthLoginEvent:
    """
    Published by auth-service after a successful login.
    Extensible for analytics, audit logs, etc.
    """
    user_id: str
    email: str
    occurred_at: str = ""

    def __post_init__(self):
        if not self.occurred_at:
            self.occurred_at = datetime.now(UTC).isoformat()

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, data: str) -> AuthLoginEvent:
        return cls(**json.loads(data))

@dataclass
class AuthSuspiciousLoginEvent:
    """
    Published by the auth-service after a successful login
    following several failed attempts.
    Consumed by email-service to send a security email
    containing a password reset link.

    reset_token: HMAC-signed one-time token used to build
                 the password reset link in the email.
    """
    user_id: str
    email: str
    username: str
    failed_attempts: int
    reset_token: str
    occurred_at: str = ""

    def __post_init__(self):
        if not self.occurred_at:
            self.occurred_at = datetime.now(UTC).isoformat()

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, data: str) -> AuthSuspiciousLoginEvent:
        return cls(**json.loads(data))

@dataclass
class NewLoginEvent:
    """
    Published by the auth-service after every successful login.
    Consumed by the email-service to notify the user of a
    new device connecting to their account (multi-device).
    """
    user_id: str
    email: str
    username: str
    device_info: str
    client_ip: str
    occurred_at: str = ""

    def __post_init__(self):
        if not self.occurred_at:
            self.occurred_at = datetime.now(UTC).isoformat()

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, data: str) -> NewLoginEvent:
        return cls(**json.loads(data))