from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import json

# --- Channel names --------------------------------------------

CHANNEL_USER_REGISTERED = "user.registered"
CHANNEL_USER_DELETED = "user.deleted"
CHANNEL_AUTH_LOGIN = "user.login"

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
            self.occurred_at = datetime.now(timezone.utc).isoformat()

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, data: str) ->  "UserRegisteredEvent":
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
            self.occurred_at = datetime.now(timezone.utc).isoformat()

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, data: str) -> "UserDeletedEvent":
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
            self.occurred_at = datetime.now(timezone.utc).isoformat()

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, data: str) -> "AuthLoginEvent":
        return cls(**json.loads(data))