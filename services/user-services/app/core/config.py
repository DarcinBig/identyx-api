from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    app_name: str = "Identyx User Service"
    debug: bool = False
    environment: str = "development"

    # Database
    database_url: str = ""

    model_config = {"env_file": ".env"}

@lru_cache()
def get_settings() -> Settings:
    return Settings()