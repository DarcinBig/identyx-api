# This router receives all /auth/* requests and forwards them to auth-service
import httpx
from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse

import app.http as http_state
from app.core.config import get_settings
from app.deps import bearer_scheme

settings = get_settings()
router = APIRouter(prefix="/auth", tags=["auth"])


def _get_client_ip(request: Request) -> str:
    """Return the real client IP.

    When ``TRUST_PROXY=true`` the gateway honours the leftmost value of the
    ``X-Forwarded-For`` header set by a trusted reverse proxy.  Otherwise it
    falls back to ``request.client.host`` (the direct peer — e.g. the Docker
    bridge IP in local dev).
    """
    if settings.trust_proxy:
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def _proxy(request: Request, path: str) -> JSONResponse:
    """
    A utility function shared by all routes on the router.

    It:
        1. Reads the body of the incoming request
        2. Retrieves the headers (Content-Type forwarder, Authorization, etc.)
        3. Sends the request to the target service via HTTPX
        4. Returns the service's response to the client as is

    In case of a network error (service down, timeout), returns a 503.
    :param request:
    :param path:
    :return:
    """
    if http_state.client is None:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"error": "Gateway not ready"},
        )
    target_url = f"{settings.auth_service_url}{path}"

    # Read the body (may be empty on GET)
    body = await request.body()

    # Filter the headers to forward
    # We exclude 'host' because it belongs to the gateway, not the target service
    headers = {
        key: value
        for key, value in request.headers.items()
        if key.lower() not in ("host", "content-length")
    }

    # Set the real client IP as the ONLY X-Forwarded-For value.
    # The inbound header from untrusted clients is stripped — the gateway
    # resolves the true IP via _get_client_ip() which either reads the
    # proxy-supplied X-Forwarded-For (TRUST_PROXY=true) or falls back to
    # request.client.host.
    client_ip = _get_client_ip(request)
    headers["x-forwarded-for"] = client_ip

    try:
        response = await http_state.client.request(
            method=request.method,
            url=target_url,
            content=body,
            headers=headers,
            params=dict(request.query_params),
        )

        try:
            content = response.json() if response.content else None
        except Exception:
            content = {"error": "Invalid response from service"}

        return JSONResponse(
            content=content,
            status_code=response.status_code,
        )

    except httpx.TimeoutException:
        return JSONResponse(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            content={"error": "Auth service timeout"},
        )

    except httpx.ConnectError:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"error": "Auth service unavailable"},
        )

@router.post("/register", operation_id="register")
async def register(request: Request):
    """
    Create a new account and start the session.

    - Sends a verification email (via Redpanda → email-service).
    - Returns an access/refresh token pair and the created user.
    - The email is normalized (lowercased + trimmed): registering the same
      email twice returns `409 Conflict`.
    - Rate limited: `RATE_LIMIT_REGISTER` (default 5 req/min per IP).

    **Body** `application/json`:
    ```json
    {
      "email": "user@example.com",
      "username": "user_2026",
      "password": "StrongPass!2026"
    }
    ```
    - `email`: valid email, normalized to lowercase.
    - `username`: 3–50 chars, `[a-zA-Z0-9_-]`.
    - `password`: min 8 chars, with 1 uppercase, 1 digit, 1 punctuation.

    **Success** `201` — `{access_token, refresh_token, token_type, user}`.
    **Errors** — `422` invalid body, `409` email already registered.
    """
    return await _proxy(request, "/auth/register")

@router.post("/login", operation_id="login")
async def login(request: Request):
    """
    Authenticate with email + password.

    - Returns a fresh access/refresh token pair and the user object.
    - Sends a "new device login" alert email when the device is unknown.
    - Brute-force protection: after `BRUTE_FORCE_MAX_ATTEMPTS` failures the
      IP is locked out for `BRUTE_FORCE_LOCKOUT_MINUTES` (based on
      X-Forwarded-For set by the gateway).
    - Rate limited: `RATE_LIMIT_LOGIN` (default 10 req/min per IP).

    **Body** `application/json`:
    ```json
    { "email": "user@example.com", "password": "StrongPass!2026" }
    ```

    **Success** `200` — `{access_token, refresh_token, token_type, user}`.
    **Errors** — `401` invalid credentials / locked out, `422` invalid body.
    """
    return await _proxy(request, "/auth/login")

@router.post("/logout", operation_id="logout", dependencies=[Depends(bearer_scheme)])
async def logout(request: Request):
    """
    End the session and revoke the tokens.

    - The refresh token in the body revokes the session (session-service).
    - The access token from the `Authorization` header is blacklisted in
      Redis (extracted by the gateway as `X-Access-Token`).

    **Auth** — `Authorization: Bearer <access_token>`.

    **Body** `application/json`:
    ```json
    { "refresh_token": "<refresh_token>" }
    ```

    **Success** `200`.
    **Errors** — `401` missing/invalid token or unknown refresh token.
    """
    if http_state.client is None:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"error": "Gateway not ready"},
        )

    # Read the original body (contains refresh_token)
    body_bytes = await request.body()

    headers = {
        key: value
        for key, value in request.headers.items()
        if key.lower() not in ("host", "content-length")
    }

    # Set the real client IP as the ONLY X-Forwarded-For value.
    client_ip = _get_client_ip(request)
    headers["x-forwarded-for"] = client_ip

    # Extract the access token from the Authorization header
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        access_token = auth_header[len("Bearer "):]
        if access_token.strip():
            headers["x-access-token"] = access_token.strip()

    try:
        response = await http_state.client.post(
            f"{settings.auth_service_url}/auth/logout",
            content=body_bytes,
            headers=headers,
        )
        try:
            content = response.json() if response.content else None
        except Exception:
            content = {"error": "Invalid response from service"}

        return JSONResponse(
            content=content,
            status_code=response.status_code,
        )
    except httpx.TimeoutException:
        return JSONResponse(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            content={"error": "Auth service timeout"},
        )
    except httpx.ConnectError:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"error": "Auth service unavailable"},
        )

@router.post("/refresh", operation_id="refresh-token")
async def refresh(request: Request):
    """
    Rotate the refresh token into a fresh access/refresh pair.

    - The refresh token is single-use: it is rotated on every call.
    - A revoked, expired or reused token returns `401`.

    **Body** `application/json`:
    ```json
    { "refresh_token": "<refresh_token>" }
    ```

    **Success** `200` — `{access_token, refresh_token, token_type}`.
    **Errors** — `401` invalid/expired/revoked refresh token, `422` invalid body.
    """
    return await _proxy(request, "/auth/refresh")

@router.get("/verify-email", operation_id="verify-email")
async def verify_email(request: Request):
    """
    Verify the email address with the one-time HMAC token from the link.

    Public route — no JWT required.

    **Query params** — `?token=<verification_token>` (received by email).

    **Success** `200` — `{message, email, is_verified}`.
    The token is single-use: a second call returns `400`.
    **Errors** — `400` missing/invalid/already-used token.
    """
    return await _proxy(request, "/auth/verify-email")

@router.post("/reset-password", operation_id="reset-password")
async def reset_password(request: Request):
    """
    Set a new password using the one-time token from the email link.

    Public route — no JWT required.

    **Body** `application/json`:
    ```json
    { "token": "<reset_token>", "new_password": "NewStrong!2026" }
    ```

    **Success** `200`.
    **Errors** — `400` invalid/expired token, `422` invalid body.
    """
    return await _proxy(request, "/auth/reset-password")

@router.post("/resend-verification", operation_id="resend-verification")
async def resend_verification(request: Request):
    """
    Re-send the verification email for an account.

    Public route — no JWT required.
    Anti-enumeration: the response is identical whether or not the email
    exists (`200` in both cases), so callers cannot probe registered emails.

    **Body** `application/json`:
    ```json
    { "email": "user@example.com" }
    ```

    **Success** `200`.
    """
    return await _proxy(request, "/auth/resend-verification")

@router.post("/confirm-deletion", operation_id="confirm-deletion")
async def confirm_deletion(request: Request):
    """
    Permanently delete an account (GDPR) using the one-time email token.

    Public route — no JWT required. The token is sent by email after a
    `POST /users/{user_id}/deletion-request` and proves the account owner
    controls the email address. This operation is irreversible.

    **Body** `application/json`:
    ```json
    { "token": "<deletion_token>" }
    ```

    **Success** `200` — `{message}`.
    **Errors** — `400` invalid/expired/already-used token, `422` invalid body.
    """
    return await _proxy(request, "/auth/confirm-deletion")

@router.get("/confirm-email-change", operation_id="confirm-email-change-get")
async def confirm_email_change_get(request: Request):
    """
    Confirm an email address change via the one-time link (GET).

    The email template embeds a clickable link that hits this GET
    endpoint. The token is extracted from the ``?token=`` query
    parameter and forwarded as a POST to the auth-service.
    """
    token = request.query_params.get("token", "")
    if not token:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "Missing token query parameter."},
        )
    if http_state.client is None:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"error": "Gateway not ready"},
        )
    try:
        response = await http_state.client.post(
            f"{settings.auth_service_url}/auth/confirm-email-change",
            json={"token": token},
            headers={"X-Internal-Key": settings.internal_api_key} if settings.internal_api_key else {},
            timeout=10.0,
        )
        try:
            content = response.json() if response.content else None
        except Exception:
            content = {"error": "Invalid response from auth service"}
        return JSONResponse(content=content, status_code=response.status_code)
    except httpx.TimeoutException:
        return JSONResponse(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            content={"error": "Auth service timeout"},
        )
    except httpx.ConnectError:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"error": "Auth service unavailable"},
        )


@router.post("/confirm-email-change", operation_id="confirm-email-change")
async def confirm_email_change(request: Request):
    """
    Apply an email address change using the one-time token.

    Public route — no JWT required. The token is sent by email to the NEW
    address after a `POST /users/{user_id}/email-change` and proves the
    caller controls the new address before it becomes active.

    **Body** `application/json`:
    ```json
    { "token": "<email_change_token>" }
    ```

    **Success** `200` — `{message}`.
    **Errors** — `400` invalid/expired/already-used token, `422` invalid body.
    """
    return await _proxy(request, "/auth/confirm-email-change")