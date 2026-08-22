from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Identyx Token Service"
    debug: bool = False
    environment: str = "development"

    # JWT
    jwt_secret_key: str = ""
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    jwt_issuer: str = "identyx"
    jwt_audience: str = "identyx-api"

    # Redis
    redis_url: str | None = None
    redis_host: str = "redis"
    redis_port: int = 6379
    redis_password: str = ""
    redis_db: int = 0

    # Shared secret for inter-service calls (X-Internal-Key).
    # Protects /tokens/generate and /tokens/revoke from direct network access.
    internal_api_key: str = ""

    # Native tenant ID (multi-tenancy Sub-step B)
    identyx_native_tenant_id: str = "00000000-0000-0000-0000-000000000001"

    model_config = {"env_file": ".env", "extra": "ignore"}

    def get_redis_url(self) -> str:
        if self.redis_url:
            return self.redis_url
        if self.redis_password:
            return (
                f"redis://:{self.redis_password}"
                f"@{self.redis_host}:{self.redis_port}"
                f"/{self.redis_db}"
            )
        return (
            f"redis://{self.redis_host}:{self.redis_port}"
            f"/{self.redis_db}"
        )

@lru_cache
def get_settings() -> Settings:
    return Settings()