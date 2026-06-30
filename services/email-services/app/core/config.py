from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional

class Settings(BaseSettings):
    app_name: str = "Identyx Email Service"
    debug: bool = False
    environment: str = "development"

    # SMTP config
    smtp_host: str = "smtp-relay.brevo.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True

    # emails_from: str = "noreply@identyx.io"
    emails_from: str = "darcinbiganiro6@gmail.com"
    emails_from_name: str = "Identyx"

    # Base URL for links in emails
    app_base_url: str = "http://gateway:8100"

    # Redis events
    redis_url: Optional[str] = None
    redis_host: str = "redis"
    redis_port: int = 6379
    redis_password: str = ""
    events_redis_db: int = 1

    model_config = {"env_file": ".env", "extra": "ignore"}

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

    def get_events_redis_url(self) -> str:
        if self.redis_url:
            return self.redis_url
        if self.redis_password:
            return (
                f"redis://:{self.redis_password}"
                f"@{self.redis_host}:{self.redis_port}"
                f"/{self.events_redis_db}"
            )
        return (
            f"redis://{self.redis_host}:{self.redis_port}"
            f"/{self.events_redis_db}"
        )

@lru_cache()
def get_settings() -> Settings:
    return Settings()