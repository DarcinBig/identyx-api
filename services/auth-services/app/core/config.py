from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Identyx Auth Service"
    debug: bool = False
    environment: str = "development"

    # PostgreSQL
    postgres_user: str
    postgres_password: str
    postgres_host: str = "postgres-auth"
    postgres_port: int = 5432
    postgres_db: str = "identyx_auth"
    database_url: str = ""

    # Redis — used only for brute-force (DB 2)
    redis_url: str | None = None
    redis_host: str = "redis"
    redis_port: int = 6379
    redis_password: str = ""

    # Anti-brute-force
    brute_force_redis_url: str = "redis://redis:6379/2"
    brute_force_max_attempts: int = 5
    brute_force_lockout_minutes: int = 15

    # Kafka / Redpanda — replaces Redis Pub/Sub
    kafka_bootstrap_servers: str = "redpanda:9092"
    kafka_client_id: str = "auth-service"

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
    user_service_url: str = "http://user-service:8001"
    token_service_url: str = "http://token-service:8003"
    session_service_url: str = "http://session-service:8004"
    email_service_url: str = "http://email-service:8005"

    model_config = {
        "env_file": ".env",
        "extra": "ignore",
    }

    @model_validator(mode="after")
    def build_database_url(self) -> Settings:
        self.database_url = (
            f"postgresql://"
            f"{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}"
            f"/{self.postgres_db}"
        )
        return self

    # def get_events_redis_url(self) -> str:
    #     if self.redis_password:
    #         return (
    #             f"redis://:{self.redis_password}"
    #             f"@{self.redis_host}:{self.redis_port}"
    #             f"/{self.events_redis_db}"
    #         )
    #     return (
    #         f"redis://{self.redis_host}"
    #         f":{self.redis_port}"
    #         f"/{self.events_redis_db}"
    #     )

@lru_cache
def get_settings() -> Settings:
    return Settings()