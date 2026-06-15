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

    emails_from: str = "noreply@identyx.io"
    emails_from_name: str = "Identyx"

    # Base URL for links in emails
    app_base_url: str = "http://localhost:8100"

    model_config = {"env_file": ".env", "extra": "ignore"}

@lru_cache()
def get_settings() -> Settings:
    return Settings()