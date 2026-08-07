from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Identyx Email Service"
    debug: bool = False
    environment: str = "development"

    # SMTP
    smtp_host: str = "smtp-relay.brevo.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True

    # Sender
    emails_from: str = "darcinbiganiro6@gmail.com"
    emails_from_name: str = "Identyx"

    # Base URL for links in emails (must be reachable from the user's browser)
    app_base_url: str = "http://localhost:8100"

    # Kafka / Redpanda — replaces Redis Pub/Sub
    kafka_bootstrap_servers: str = "redpanda:9092"
    kafka_consumer_group_id: str = "email-service-group"
    kafka_client_id: str = "email-service"

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()