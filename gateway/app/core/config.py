from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    app_name: str = "Identyx Gateway"
    debug: bool = False
    environment: str = "development"
    gateway_port: int = 8100

    # URLs of internal services
    user_service_url: str = "http://localhost:8001"
    auth_service_url: str = "http://localhost:8002"
    token_service_url: str = "http://localhost:8003"
    session_service_url: str = "http://localhost:8004"
    email_service_url: str = "http://localhost:8005"

    # JWT (gateway-side validation)
    jwt_secret_key: str = ""
    jwt_algorithm: str = "HS256"

    # Redis (rate limiting)
    redis_host: str = "localhost"
    redis_port: int = 6379
    # redis_url: str = "redis://redis:6379"

    model_config = {"env_file": ".env", "extra": "ignore"}

@lru_cache()
def get_settings() -> Settings:
    return Settings()