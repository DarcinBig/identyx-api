from fastapi import HTTPException, UploadFile, status

from app.core.config import get_settings
from app.storage.base import StorageProvider
from app.storage.github_upload import GithHubStorageProvider

settings = get_settings()

# Allowed extensions and MIME types
ALLOWED_CONTENT_TYPES = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp"
}
ALLOWED_EXTENSIONS = {".jpeg", ".jpg", ".png", ".webp"}

# Max size: 5 MB
MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024

def _get_provider() -> StorageProvider:
    """
    Returns the active storage provider according to the configuration.

    Add a new provider here when it is implemented:
    elif settings.storage_provider == "s3":
    return S3StorageProvider()
    elif settings.storage_provider == "cloudinary":
    return CloudinaryStorageProvider()
    """
    if settings.storage_provider == "github":
        return GithHubStorageProvider()
    raise ValueError(
        f"Unknown storage provider: '{settings.storage_provider}'."
        f"Supported: 'github'."
        f"Future: 's3', 'cloudinary', 'azure'."
    )

class StorageService:
    """
    Avatar management service.

    Responsibilities:
        - Validate the file (type, size)
        - Construct the filename (user_id + extension)
        - Delegate upload/deletion to the active provider
        - Return the public raw URL
    """
    def __init__(self):
        self.provider = _get_provider()

    async def upload_avatar(self, user_id: str, file: UploadFile) -> str:
        """
       Validates and uploads a user's avatar.

        The file is named with the user's UUID
        to ensure uniqueness and allow for overwriting
        when a photo is changed.

        Returns the raw public URL of the uploaded avatar.
        """
        # Validate the MIME type
        if file.content_type not in ALLOWED_CONTENT_TYPES:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=(
                    f"File type '{file.content_type}' not allowed."
                    f"Allowed: jpg, jpeg, png, webp"
                ),
            )

        # Read the content
        content = await file.read()
        # Validate the size
        if len(content) > MAX_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail="File too large. Maximum size is 5 MB."
            )

        # Construct the filename
        # Format: {user_id}.{extension}
        # Ex: "550e8400-e29b-41d4-a716.jpg"
        extension = _get_extension(file.content_type)
        filename = f"{user_id}{extension}"

        # Upload via the active provider
        raw_url = await self.provider.upload(
            file_content=content,
            filename=filename,
            content_type=file.content_type,
        )
        return raw_url

    async def delete_avatar(self, user_id: str) -> bool:
        """
        Deletes a user's avatar.

        Tries all possible formats (jpg, png, webp)
        because we don't necessarily know which format was uploaded.

        Returns True if a file was deleted, False otherwise.
        """
        for ext in ALLOWED_EXTENSIONS:
            filename = f"{user_id}{ext}"
            deleted = await self.provider.delete(filename)
            if deleted:
                return True
        return False

def _get_extension(content_type: str) -> str:
    """Returns the file extension corresponding to the MIME type"""
    mapping = {
        "image/jpeg": ".jpeg",
        "image/jpg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
    }
    return mapping.get(content_type, ".jpg")