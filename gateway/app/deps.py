from fastapi.security import HTTPBearer

bearer_scheme = HTTPBearer(
    auto_error=False,
    description="JWT access token returned by POST /v1/auth/login",
)
