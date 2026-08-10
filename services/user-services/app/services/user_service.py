from fastapi import HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.repositories.user_repo import UserRepository
from app.schemas.user import AvatarResponse, UserCreate, UserListResponse, UserResponse, UserUpdate
from app.storage.service import StorageService

settings = get_settings()

class UserService:
    """
    User service business logic.

    Manages:
        - CRUD operations on users
        - Uploading/deleting/reverting avatars to default settings
    """
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = UserRepository(db)
        self.storage = StorageService()

    async def create_user(self, data: UserCreate) -> UserResponse:
        """
        Creates a new user.
        The profile picture is automatically resolved as "default"
        """
        if await self.repo.get_by_email(data.email):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already registered",
            )
        if await self.repo.get_by_username(data.username):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Username already taken",
            )
        user = await self.repo.create(data)
        return UserResponse.from_user(user)

    async def get_user_by_id(self, user_id: str) -> UserResponse:
        user = await self.repo.get_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
        return UserResponse.from_user(user)

    async def get_user_by_email(self, email: str) -> UserResponse:
        """Internal endpoint for auth-service"""
        user = await self.repo.get_by_email(email)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
        return UserResponse.from_user(user)

    async def update_user(self, user_id: str, data: UserUpdate) -> UserResponse:
        existing_user = await self.repo.get_by_id(user_id)
        if not existing_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
        if data.email and data.email.lower() != existing_user.email:
            if await self.repo.get_by_email(data.email):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Email already registered",
                )
        if data.username and data.username != existing_user.username:
            if await self.repo.get_by_username(data.username):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Username already taken",
                )
        user = await self.repo.update(user_id, data)
        return UserResponse.from_user(user)

    async def delete_user(self, user_id: str) -> dict:
        # Also remove the avatar if the user had one.
        user = await self.repo.get_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
        if user.avatar_provider == "upload":
            await self.storage.delete_avatar(user_id)

        deleted = await self.repo.delete(user_id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
        return {"message": "User deleted successfully"}

    async def list_users(self, page: int = 1, page_size: int = 20) -> UserListResponse:
        users = await self.repo.get_all(page=page, page_size=page_size)
        total = await self.repo.count()
        return UserListResponse(
            users=[UserResponse.from_user(user) for user in users],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def upload_avatar(self, user_id: str, file: UploadFile) -> AvatarResponse:
        """
        Upload an avatar for a user.

        Flow:
            1. Verifies that the user exists
            2. Validates the file (type + size) via StorageService
            3. Uploads to GitHub (or future provider)
            4. Updates avatar_url and avatar_provider in the database
            5. Returns the raw public URL

        The existing file is automatically overwritten
        (same filename = same user_id).
        """
        user = await self.repo.get_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        # Upload via the active provider (GitHub for V1)
        raw_url = await self.storage.upload_avatar(
            user_id=user_id,
            file=file,
        )

        # DB update
        await self.repo.update_avatar(
            user_id=user_id,
            avatar_url=raw_url,
            avatar_provider="upload",
        )

        return AvatarResponse(
            avatar_url=raw_url,
            avatar_provider="upload",
            message="Avatar uploaded successfully",
        )

    async def delete_avatar(self, user_id: str) -> AvatarResponse:
        """
        Removes a user's avatar and reverts to the default photo.

        Flow:
            1. Checks that the user exists
            2. Deletes the file from storage (if provider = upload)
            3. Sets avatar_url to None and avatar_provider to "default" in the database
            4. Returns the URL of the default avatar

            If the user already had the default photo, there's no error —
            the default URL is simply returned.

        Future note: if the provider is "google", "linkedin", etc.,
        the system will also revert to "default" without affecting the external storage.
        """
        user = await self.repo.get_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        # Remove from storage only if it was a user upload
        if user.avatar_provider == "upload":
            await self.storage.delete_avatar(user_id)

        # Reset to default in database
        await self.repo.update_avatar(
            user_id=user_id,
            avatar_url=None,
            avatar_provider="default",
        )

        default_url = settings.get_default_avatar_url()
        return AvatarResponse(
            avatar_url=default_url,
            avatar_provider="default",
            message="Avatar reset to default",
        )

    async def get_avatar_url(self, user_id: str) -> AvatarResponse:
        """
        Returns the raw URL of the user's avatar.
        Always a valid URL — never None.
        """
        user = await self.repo.get_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        url = user.avatar_url or settings.get_default_avatar_url()
        return AvatarResponse(
            avatar_url=url,
            avatar_provider=user.avatar_provider,
            message="Avatar URL retrieved",
        )

    # --- Email verification (called only by auth-service) -----------------------------------

    async def store_verification_token(
        self,
        user_id: str,
        raw_token: str,
    ) -> None:
        """
        Stores the email verification token in DB.
        Called by auth-service after register (via internal endpoint).
        Only the SHA-256 hash of the raw token is stored.
        """
        from app.repositories.email_verifications_repo import EmailVerificationRepository

        repo = EmailVerificationRepository(self.db)
        await repo.create(
            user_id=user_id,
            raw_token=raw_token,
            expires_in_hours=24,
        )

    async def check_verification_token(
        self,
        user_id: str,
        raw_token: str,
    ) -> dict:
        """
        Checks the token in DB:
          - Does it exist?
          - Does it belong to user_id?
          - Not expired?
          - Not already used?
        """
        from datetime import UTC, datetime

        from app.repositories.email_verifications_repo import EmailVerificationRepository

        repo = EmailVerificationRepository(self.db)
        verification = await repo.get_by_token(raw_token)

        if not verification:
            return {"valid": False, "detail": "Verification token not found."}

        if verification.user_id != user_id:
            return {"valid": False, "detail": "Invalid verification token."}

        if verification.is_used:
            return {"valid": False, "detail": "Verification token already used."}

        now = datetime.now(UTC)
        expires_at = verification.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)

        if expires_at < now:
            return {"valid": False, "detail": "Verification token expired."}

        return {"valid": True, "detail": ""}

    async def confirm_email_verification(
        self,
        user_id: str,
        raw_token: str,
    ) -> dict:
        """
        Atomic operation:
          1. Mark the token as used
          2. Mark the email as verified (is_verified=True)

        Returns the updated profile.
        """
        from app.repositories.email_verifications_repo import EmailVerificationRepository

        # Retrieve the token
        repo = EmailVerificationRepository(self.db)
        verification = await repo.get_by_token(raw_token)

        if not verification:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Verification token not found.",
            )

        # Mark the token as used
        await repo.mark_as_used(verification.id)

        # Mark the email as verified
        user = await self.repo.update(
            user_id=user_id,
            data=UserUpdate(is_verified=True),
        )

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found.",
            )

        return {
            "email": user.email,
            "is_verified": user.is_verified,
        }

    # --- Password reset tokens (called only by auth-service) ------------------------------

    async def store_password_reset_token(
        self,
        user_id: str,
        raw_token: str,
    ) -> None:
        """
        Stores a password reset token in DB.
        Called by auth-service when a suspicious login is detected
        (via internal endpoint).
        Only the SHA-256 hash of the raw token is stored.
        """
        from app.repositories.password_reset_repo import PasswordResetRepository

        repo = PasswordResetRepository(self.db)
        await repo.create(
            user_id=user_id,
            raw_token=raw_token,
            expires_in_minutes=60,
        )

    async def check_password_reset_token(
        self,
        user_id: str,
        raw_token: str,
    ) -> dict:
        """
        Checks the password reset token in DB:
          - Does it exist?
          - Does it belong to user_id?
          - Not expired?
          - Not already used?
        """
        from datetime import UTC, datetime

        from app.repositories.password_reset_repo import PasswordResetRepository

        repo = PasswordResetRepository(self.db)
        reset = await repo.get_by_token(raw_token)

        if not reset:
            return {"valid": False, "detail": "Password reset token not found."}

        if reset.user_id != user_id:
            return {"valid": False, "detail": "Invalid password reset token."}

        if reset.is_used:
            return {"valid": False, "detail": "Password reset token already used."}

        now = datetime.now(UTC)
        expires_at = reset.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)

        if expires_at < now:
            return {"valid": False, "detail": "Password reset token expired."}

        return {"valid": True, "detail": ""}

    async def confirm_password_reset(
        self,
        user_id: str,
        raw_token: str,
    ) -> dict:
        """
        Marks the password reset token as used.
        Called by auth-service after the password has been changed.
        Returns the updated profile.
        """
        from app.repositories.password_reset_repo import PasswordResetRepository

        repo = PasswordResetRepository(self.db)
        reset = await repo.get_by_token(raw_token)

        if not reset:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password reset token not found.",
            )

        await repo.mark_as_used(reset.id)

        user = await self.repo.get_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found.",
            )

        return {
            "email": user.email,
            "confirmed": True,
        }

    # --- Account deletion tokens (GDPR, called only by auth-service) ------------------------

    async def store_deletion_request_token(
        self,
        user_id: str,
        raw_token: str,
    ) -> None:
        """
        Stores an account deletion confirmation token in DB.
        Called by auth-service when the owner requests a GDPR deletion.
        Only the SHA-256 hash of the raw token is stored.
        """
        from app.repositories.deletion_request_repo import DeletionRequestRepository

        repo = DeletionRequestRepository(self.db)
        await repo.create(
            user_id=user_id,
            raw_token=raw_token,
            expires_in_hours=24,
        )

    async def check_deletion_request_token(
        self,
        user_id: str,
        raw_token: str,
    ) -> dict:
        """
        Checks the deletion confirmation token in DB:
          - Does it exist?
          - Does it belong to user_id?
          - Not expired?
          - Not already used?
        """
        from datetime import UTC, datetime

        from app.repositories.deletion_request_repo import DeletionRequestRepository

        repo = DeletionRequestRepository(self.db)
        deletion_request = await repo.get_by_token(raw_token)

        if not deletion_request:
            return {"valid": False, "detail": "Deletion token not found."}

        if deletion_request.user_id != user_id:
            return {"valid": False, "detail": "Invalid deletion token."}

        if deletion_request.is_used:
            return {"valid": False, "detail": "Deletion token already used."}

        now = datetime.now(UTC)
        expires_at = deletion_request.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)

        if expires_at < now:
            return {"valid": False, "detail": "Deletion token expired."}

        return {"valid": True, "detail": ""}

    async def confirm_deletion(
        self,
        user_id: str,
        raw_token: str,
    ) -> dict:
        """
        Atomic GDPR deletion:
          1. Mark the deletion token as used (single-use)
          2. Permanently delete the user profile (+ avatar if any)

        Returns the email of the deleted account.
        """
        from app.repositories.deletion_request_repo import DeletionRequestRepository

        repo = DeletionRequestRepository(self.db)
        deletion_request = await repo.get_by_token(raw_token)

        if not deletion_request:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Deletion token not found.",
            )

        # Retrieve the email BEFORE deleting the user
        user = await self.repo.get_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found.",
            )
        email = user.email

        # Mark the token as used (single-use)
        await repo.mark_as_used(deletion_request.id)

        # Remove the avatar from storage if it was a user upload
        if user.avatar_provider == "upload":
            try:
                await self.storage.delete_avatar(user_id)
            except Exception:
                pass

        # Permanently delete the profile
        deleted = await self.repo.delete(user_id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found.",
            )

        return {
            "email": email,
            "deleted": True,
        }

    # --- Email change tokens (called only by auth-service) ---------------------------------

    async def store_email_change_token(
        self,
        user_id: str,
        raw_token: str,
        pending_email: str,
    ) -> None:
        """
        Stores an email change request in DB.
        Called by auth-service when the owner asks to change their email.
        Only the SHA-256 hash of the raw token is stored.
        """
        from app.repositories.email_change_repo import EmailChangeRepository

        repo = EmailChangeRepository(self.db)
        await repo.create(
            user_id=user_id,
            raw_token=raw_token,
            pending_email=pending_email,
            expires_in_hours=24,
        )

    async def check_email_change_token(
        self,
        user_id: str,
        raw_token: str,
    ) -> dict:
        """
        Checks the email change token in DB:
          - Does it exist?
          - Does it belong to user_id?
          - Not expired?
          - Not already used?
        """
        from datetime import UTC, datetime

        from app.repositories.email_change_repo import EmailChangeRepository

        repo = EmailChangeRepository(self.db)
        email_change = await repo.get_by_token(raw_token)

        if not email_change:
            return {"valid": False, "detail": "Email change token not found."}

        if email_change.user_id != user_id:
            return {"valid": False, "detail": "Invalid email change token."}

        if email_change.is_used:
            return {"valid": False, "detail": "Email change token already used."}

        now = datetime.now(UTC)
        expires_at = email_change.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)

        if expires_at < now:
            return {"valid": False, "detail": "Email change token expired."}

        return {"valid": True, "detail": ""}

    async def confirm_email_change(
        self,
        user_id: str,
        raw_token: str,
    ) -> dict:
        """
        Atomic email change:
          1. Mark the email change token as used (single-use)
          2. Apply the pending email (replaces the current one)

        The new email has been proven by the confirmation link,
        so is_verified is set to True.
        Returns the updated profile.
        """
        from app.repositories.email_change_repo import EmailChangeRepository

        repo = EmailChangeRepository(self.db)
        email_change = await repo.get_by_token(raw_token)

        if not email_change:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email change token not found.",
            )

        # Mark the token as used (single-use)
        await repo.mark_as_used(email_change.id)

        # The target email could have been taken between the request
        # and the confirmation — check before applying.
        if await self.repo.get_by_email(email_change.pending_email):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already registered.",
            )

        # Apply the pending email
        user = await self.repo.update(
            user_id=user_id,
            data=UserUpdate(
                email=email_change.pending_email,
                is_verified=True,
            ),
        )

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found.",
            )

        return {
            "email": user.email,
            "confirmed": True,
        }