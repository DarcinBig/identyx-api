from typing import Optional
from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    app_name: str = "Identyx Token Service"
    debug: bool = False
    environment: str = "development"

    # JWT
    jwt_secret_key: str = ""
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # Redis
    redis_url: Optional[str] = None
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: str = ""
    redis_db: int = 0

    model_config = {"env_file": ".env.local", "extra": "ignore"}

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

@lru_cache()
def get_settings() -> Settings:
    return Settings()