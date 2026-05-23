import base64
import httpx

from app.storage.base import StorageProvider
from app.core.config import get_settings

settings = get_settings()

class GithHubStorageProvider(StorageProvider):
    """
    Storage provider using GitHub as a CDN for avatars.

    How it works:
        - Upload: PUT https://api.github.com/repos/{owner}/{repo}/contents/{path}
        - Delete: DELETE https://api.github.com/repos/{owner}/{repo}/contents/{path}
        - Read: The raw URL is public; no API call is needed.

    Raw URL of a file:
        https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}

    Prerequisites:
        - A public GitHub repository (so that raw URLs are accessible)
        - A GitHub token with "repo" permissions (read + write contents)
        - A default.png file already present in the repository.
    """
    BASE_API = "https://api.github.com"

    def __init__(self):
        self.owner = settings.github_owner
        self.repo = settings.github_repo
        self.branch = settings.github_branch
        self.folder = settings.github_avatars_folder

        if not settings.github_token:
            raise ValueError(
                "GITHUB_TOKEN is not set in .env. "
                "Generate a fine-grained token with Contents: Read and Write "
                "on the repository and add it to your .env file."
            )
        
        self.headers = {
            "Authorization": f"Bearer {settings.github_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def _file_path(self, filename: str) -> str:
        """File path in the repo"""
        return f"{self.folder}/{filename}"

    def _raw_url(self, filename: str) -> str:
        """Public raw URL of the file"""
        return (
            f"https://raw.githubusercontent.com/"
            f"{self.owner}/{self.repo}/{self.branch}/"
            f"{self.folder}/{filename}"
        )

    def _api_url(self, filename: str) -> str:
        """GitHub Contents API URL for this file"""
        path = self._file_path(filename)
        return f"{self.BASE_API}/repos/{self.owner}/{self.repo}/contents/{path}"

    async def _get_file_sha(self, filename: str) -> str | None:
        """
        Retrieves the SHA of the existing file.
        Required by the GitHub API to update or delete a file.
        Returns None if the file does not exist.
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                self._api_url(filename),
                headers=self.headers,
            )
            if response.status_code == 200:
                return response.json().get("sha")
            return None

    async def upload(self, file_content: bytes, filename: str, content_type: str) -> str:
        """
        Upload an avatar to GitHub.

        If the file already exists (same name = same user),
        it is replaced (updated via SHA).

        Returns the public raw URL.
        """
        # Content encoding
        encoded = base64.b64encode(file_content).decode("utf-8")
        # Retrieve the SHA if the file already exists (necessary for update)
        sha = await self._get_file_sha(filename)

        payload: dict = {
            "message": f"Upload avatar {filename}",
            "content": encoded,
            "branch": self.branch,
        }
        if sha:
            # Updating an existing file
            payload["sha"] = sha

        async with httpx.AsyncClient() as client:
            response = await client.put(
                self._api_url(filename),
                headers=self.headers,
                json=payload,
            )
        if response.status_code not in (200, 201):
            raise RuntimeError(
                f"GitHub upload failed: {response.status_code} — "
                f"{response.text}"
            )
        return self._raw_url(filename)

    async def delete(self, filename: str) -> bool:
        """
        Delete an avatar from GitHub.
        Returns True if the file was deleted, False otherwise.
        """
        sha = await self._get_file_sha(filename)
        if not sha:
            return False

        payload = {
            "message": f"Delete avatar {filename}",
            "sha": sha,
            "branch": self.branch,
        }
        async with httpx.AsyncClient() as client:
            response = await client.request(
                method="DELETE",
                url=self._api_url(filename),
                headers=self.headers,
                json=payload,
            )
        return response.status_code == 200

    async def exists(self, filename: str) -> bool:
        """Checks if the file exists on GitHub."""
        sha = await self._get_file_sha(filename)
        return sha is not None

