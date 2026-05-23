import re
import string
from datetime import datetime
from pydantic import BaseModel, EmailStr, field_validator, model_validator

from app.core.config import get_settings

settings = get_settings()

USERNAME_MIN = 3
USERNAME_MAX = 50
USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")

class UserCreate(BaseModel):
    """
    Data for user creation.
    POST /users/
    """
    email: EmailStr
    username: str
    password: str

    @field_validator("username")
    @classmethod
    def validate_username(cls, validator: str) -> str:
        my_validator = validator.strip()
        if (len(my_validator) < USERNAME_MIN or len(my_validator) > USERNAME_MAX or
            not USERNAME_PATTERN.match(my_validator)):
            raise ValueError(
                f"Username must be between {USERNAME_MIN} and {USERNAME_MAX} characters, and can only contain letters, numbers, _ and -."
            )
        return my_validator

    @field_validator("password")
    @classmethod
    def validate_password(cls, validator: str) -> str:
        if len(validator) < 8 or not any(char.isupper() for char in validator) or not any(char.isdigit() for char in validator) or not any(char in string.punctuation for char in validator):
            raise ValueError("Password must be at least 8 characters, with 1 digit and 1 punctuation.")
        return validator

class UserUpdate(BaseModel):
    """
    Partial update of a user.
    PATCH /users/{user_id}
    """
    email: EmailStr | None = None
    username: str | None = None

    @field_validator("username")
    @classmethod
    def validate_username(cls, validator: str | None) -> str | None:
        if validator is None:
            return None
        my_validator = validator.strip()
        if (len(my_validator) < USERNAME_MIN or len(my_validator) > USERNAME_MAX or
                not USERNAME_PATTERN.match(my_validator)):
            raise ValueError(
                f"Username must be between {USERNAME_MIN} and {USERNAME_MAX} characters, and can only contain letters, numbers, _ and -."
            )
        return my_validator

    @model_validator(mode="after")
    def at_least_one_field(self) -> "UserUpdate":
        if self.email is None and self.username is None:
            raise ValueError("Username or email must be provided.")
        return self

class UserResponse(BaseModel):
    """
    Data returned to the client.

    avatar_url: Public raw URL of the avatar.
                If None is present in the database, the default avatar URL is returned.
                This ensures the client always receives a valid URL.

    avatar_provider: Indicates the avatar source.
    """
    id: str
    email: str
    username: str
    is_active: bool
    is_verified: bool
    avatar_url: str             # never None on the client side
    avatar_provider: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_user(cls, user) -> "UserResponse":
        """
        Constructs the response from a User model.
        Resolves the default URL if the user has no avatar.
        """
        return cls(
            id=user.id,
            email=user.email,
            username=user.username,
            is_active=user.is_active,
            is_verified=user.is_verified,
            avatar_url=user.avatar_url or settings.get_default_avatar_url(),
            avatar_provider=user.avatar_provider,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )

class AvatarResponse(BaseModel):
    """
    Response after uploading or deleting an avatar.
    """
    avatar_url: str
    avatar_provider: str
    message: str

class UserListResponse(BaseModel):
    """Paged response for the list of users."""
    users: list[UserResponse]
    total: int
    page: int
    page_size: int