from abc import ABC, abstractmethod


class StorageProvider(ABC):
    """
    Abstract interface for avatar storage providers.

    Any new provider (S3, Cloudinary, Azure Blob, etc.)
    must inherit from this class and implement these three methods.

    For this version (V1), GitHub is the only implemented provider.

    In future versions: integrate S3, Cloudinary, etc.
    """
    @abstractmethod
    async def upload(
            self,
            file_content: bytes,
            filename: str,
            content_type: str,
    ) -> str:
        """
        Upload a file and return its public raw URL.

        :params:
            file_content: Binary content of the file
            filename: File name (e.g., "user_uuid.jpg")
            content_type: MIME type (e.g., "image/jpeg")

        :return:
            Public raw URL of the uploaded file
        """

    @abstractmethod
    async def delete(self, filename: str) -> bool:
        """
        Deletes a file from storage.

        :param:
            filename: name of the file to delete

        :return:
            True if deleted, False if not found
        """

    @abstractmethod
    async def exists(self, filename: str) -> bool:
        """
        Checks if a file exists in storage.

        :param:
            filename: Name of the file to check

        :return:
            True if exists, False otherwise
        """