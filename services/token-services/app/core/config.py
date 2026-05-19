from ast import Dict

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
    redis_url: str = "redis://localhost:6379"

    model_config = {"env_file": ".env"}

@lru_cache()
def get_settings() -> Settings:
    return Settings()