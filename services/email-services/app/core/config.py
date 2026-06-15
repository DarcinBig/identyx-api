from pydantic_settings import BaseSettings
from functools import lru_cache

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
    app_base_url: str = "http://localhost:8100"

    # Redis events
    events_redis_host: str = "localhost"
    events_redis_port: int = 6379
    events_redis_password: str = ""
    events_redis_db: int = 1

    model_config = {"env_file": ".env", "extra": "ignore"}

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