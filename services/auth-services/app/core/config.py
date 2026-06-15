from pydantic_settings import BaseSettings
from pydantic import model_validator
from functools import lru_cache

class Settings(BaseSettings):
    app_name: str = "Identyx Auth Service"
    debug: bool = False
    environment: str = "development"

    # PostgreSQL
    postgres_user: str
    postgres_password: str
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "identyx_auth"

    database_url: str = ""

    # Redis
    # redis_url: str = "redis://localhost:6379"

    # Redis events
    events_redis_host: str = "localhost"
    events_redis_port: int = 6379
    events_redis_password: str = ""
    events_redis_db: int = 1

    # JWT
    jwt_secret_key: str = ""
    jwt_algorithm: str = "HS256"
    access_token_expires_minutes: int = 30
    refresh_token_expires_days: int = 7

    # Argon2id - OWAP parameters 2024
    argon2_time_cost: int = 2
    argon2_memory_cost: int = 65536 # 64 MB
    argon2_parallelism: int = 2
    argon2_hash_len: int = 32
    argon2_salt_len: int = 16

    # Internal services URLs
    user_service_url: str = "http://localhost:8001"
    token_service_url: str = "http://localhost:8003"
    session_service_url: str = "http://localhost:8004"
    email_service_url: str = "http://localhost:8005"

    model_config = {
        "env_file": ".env",
        "extra": "ignore",
    }

    @model_validator(mode="after")
    def build_database_url(self) -> "Settings":
        self.database_url = (
            f"postgresql://"
            f"{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}"
            f"/{self.postgres_db}"
        )
        return self

    def get_events_redis_url(self) -> str:
        if self.events_redis_password:
            return (
                f"redis://:{self.events_redis_password}"
                f"@{self.events_redis_host}:{self.events_redis_port}"
                f"/{self.events_redis_db}"
            )
        return (
            f"redis://{self.events_redis_host}"
            f":{self.events_redis_port}"
            f"/{self.events_redis_db}"
        )

@lru_cache()
def get_settings() -> Settings:
    return Settings()