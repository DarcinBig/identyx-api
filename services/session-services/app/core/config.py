from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Identyx Session Service"
    debug: bool = False
    environment: str = "development"

    # Database
    database_url: str = ""

    # PostgreSQL
    postgres_user: str
    postgres_password: str
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "identyx_sessions"

    # Redis
    redis_url: str = "redis://localhost:6379"
    # events_redis_host: str = "redis"
    # events_redis_port: int = 6379
    # events_redis_password: str = ""
    # events_redis_db: int = 1

    # JWT
    refresh_token_expire_days: int = 7

    # Multi-device — max active sessions per user
    # When reached, the oldest active session is revoked on the next login
    max_sessions_per_user: int = 5

    model_config = {"env_file": ".env", "extra": "ignore"}

    @model_validator(mode="after")
    def build_database_url(self) -> Settings:
        self.database_url = (
            f"postgresql://"
            f"{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}"
            f"/{self.postgres_db}"
        )
        return self

@lru_cache
def get_settings() -> Settings:
    return Settings()