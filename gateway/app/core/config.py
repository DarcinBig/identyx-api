from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Identyx Gateway"
    debug: bool = False
    environment: str = "development"
    gateway_port: int = 8100

    # Public base URL (used to populate the OpenAPI `servers` list)
    app_base_url: str = "http://localhost:8100"

    # URLs of internal services
    user_service_url: str = "http://user-service:8001"
    auth_service_url: str = "http://auth-service:8002"
    token_service_url: str = "http://token-service:8003"
    session_service_url: str = "http://session-service:8004"
    email_service_url: str = "http://email-service:8005"
    application_service_url: str = "http://application-service:8006"

    # JWT (gateway-side validation)
    jwt_secret_key: str = ""
    jwt_algorithm: str = "HS256"

    # Shared secret for gateway → service internal calls
    # (e.g. POST /auth/internal/verify-password). Must match root .env.
    internal_api_key: str = ""

    # Rate Limiting
    rate_limit_redis_url: str = "redis://redis:6379/2"
    rate_limit_global: int = 100            # req/min per IP
    rate_limit_login: int = 10              # req/min per IP on /auth/login
    rate_limit_register: int = 5            # req/min per IP on /auth/register
    rate_limit_reset_password: int = 3      # req/min per IP on /auth/reset-password
    rate_limit_verify_email: int = 5        # req/min per IP on /auth/verify-email + resend-verification
    rate_limit_refresh: int = 20            # req/min per IP on /auth/refresh
    rate_limit_sessions: int = 60           # req/min per IP on /sessions/*
    rate_limit_per_key_rpm: int = 600       # req/min per API key (per application)

    # Proxy — set to true when a trusted reverse proxy (Cloudflare, nginx…)
    # sits in front of the gateway and sets X-Forwarded-For with the real
    # client IP.  When false (default), the gateway uses request.client.host
    # which is the direct peer IP (e.g. Docker bridge 172.x).
    trust_proxy: bool = False

    # CORS
    cors_origins: str = "http://localhost:3000,http://localhost:8000"

    # Redis (rate limiting)
    redis_host: str = "localhost"
    redis_port: int = 6379
    # redis_url: str = "redis://redis:6379"

    model_config = {"env_file": ".env", "extra": "ignore"}

    def get_cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

@lru_cache
def get_settings() -> Settings:
    return Settings()