from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Identyx Application Service"
    debug: bool = False
    environment: str = "development"

    # PostgreSQL
    postgres_user: str
    postgres_password: str
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "identyx_applications"

    database_url: str = ""

    # Redis — key resolution cache (DB 3)
    redis_url: str | None = None
    redis_host: str = "redis"
    redis_port: int = 6379
    redis_password: str = ""
    redis_db: int = 3
    api_key_cache_ttl_seconds: int = 60

    # Shared secret for inter-service calls (X-Internal-Key).
    # Protects the /applications/* endpoints from direct network access.
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

    def get_redis_url(self) -> str:
        if self.redis_url:
            return self.redis_url
        if self.redis_password:
            return (
                f"redis://:{self.redis_password}"
                f"@{self.redis_host}:{self.redis_port}"
                f"/{self.redis_db}"
            )
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
