from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Identyx User Service"
    debug: bool = False
    environment: str = "development"

    # PostgreSQL
    postgres_user: str
    postgres_password: str
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "identyx_users"

    database_url: str = ""

    # GitHub Storage (upload files | next: Cloudinary/AWS S3)
    github_token: str = ""
    github_owner: str = "DarcinBig"
    github_repo: str = "identyx-api"
    github_branch: str = "main"
    github_avatars_folder: str = "avatars"

    # Active storage provider
    # GitHub is used for this V1; in future versions,
    # we will switch to Cloudinary or AWS S3 as needed.
    storage_provider: str = "github"

    # Shared secret for inter-service calls (X-Internal-Key).
    # Protects the /users/internal/* endpoints from direct network access.
    internal_api_key: str = ""

    model_config = {"env_file": ".env"}

    @model_validator(mode="after")
    def build_database_url(self) -> Settings:
        """
        Constructs DATABASE_URL from the separated variables.
        Automatically called after field validation.
        """
        self.database_url = (
            f"postgresql://"
            f"{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}"
            f"/{self.postgres_db}"
        )
        return self

    def get_default_avatar_url(self) -> str:
        """Makes the default avatar URL with the actual values."""
        return (
            f"https://raw.githubusercontent.com/"
            f"{self.github_owner}/{self.github_repo}/"
            f"{self.github_branch}/{self.github_avatars_folder}/default.png"
        )

@lru_cache
def get_settings() -> Settings:
    return Settings()   #type: ignore[call-arg]