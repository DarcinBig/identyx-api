"""
Internal routes of application-service.

None of these are exposed to clients directly — the gateway proxies them and
adds the shared `X-Internal-Key` header. The public-facing surface is:
  - `GET /v1/public/applications/me` → proxies `GET /applications/me`
  - `POST /applications/verify-key` → called by the gateway on every request

All routes are hidden from the OpenAPI schema (`include_in_schema=False`).
"""

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies import require_internal_key
from app.schemas.application import (
    ApplicationCreate,
    ApplicationCreatedResponse,
    ApplicationKeyCreatedResponse,
    ApplicationResponse,
    ApplicationUpdate,
    PublicApplicationInfo,
    RevokeKeyResponse,
    VerifyKeyRequest,
    VerifyKeyResult,
)
from app.services.application_service import ApplicationService

router = APIRouter(prefix="/applications", tags=["applications"])


def get_application_service(db: AsyncSession = Depends(get_db)) -> ApplicationService:
    return ApplicationService(db)


# ─── Admin endpoints (break-glass) ─────────────────────────────────


@router.post(
    "/",
    response_model=ApplicationCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an application + first key pair",
    operation_id="create_application",
    include_in_schema=False,
)
async def create_application(
    data: ApplicationCreate,
    service: ApplicationService = Depends(get_application_service),
    _: None = Depends(require_internal_key),
):
    """
    Creates an application (1 app = 1 tenant) and issues its first
    publishable + secret key pair. The full keys are returned exactly once.
    """
    return await service.create_application(data)


# ─── Key resolution (hot path — called by the gateway) ─────────────


@router.post(
    "/verify-key",
    response_model=VerifyKeyResult,
    status_code=status.HTTP_200_OK,
    summary="Resolve an API key into a tenant (internal)",
    operation_id="verify_key",
    include_in_schema=False,
)
async def verify_key(
    data: VerifyKeyRequest,
    service: ApplicationService = Depends(get_application_service),
    _: None = Depends(require_internal_key),
):
    """
    Resolves `{key_id, secret}` into `{tenant_id, application_id, key_type,
    allowed_origins, status}`. Returns 401 when the key is unknown, revoked,
    mismatched, or its application is suspended.
    """
    result = await service.verify_key(data.key_id, data.secret)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key.",
        )
    return result


# ─── Public introspection (proxied by the gateway) ─────────────────


@router.get(
    "/me",
    response_model=PublicApplicationInfo,
    status_code=status.HTTP_200_OK,
    summary="Non-sensitive app metadata for the presented key",
    operation_id="me",
    include_in_schema=False,
)
async def me(
    service: ApplicationService = Depends(get_application_service),
    x_identyx_key: str | None = Header(default=None),
    _: None = Depends(require_internal_key),
):
    """
    Returns only non-sensitive metadata of the application associated with
    the key presented in `X-Identyx-Key`: application_id, name,
    allowed_origins, status, key_type. Never key_hash / webhook_secret_hash.
    """
    if not x_identyx_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key.",
        )
    info = await service.introspect_key(x_identyx_key)
    if info is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key.",
        )
    return info


# ─── Admin endpoints (break-glass) — parameterized ─────────────────


@router.post(
    "/{application_id}/keys",
    response_model=ApplicationKeyCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Rotate keys (issue a new pair, keep old ones active)",
    operation_id="rotate_keys",
    include_in_schema=False,
)
async def rotate_keys(
    application_id: str,
    service: ApplicationService = Depends(get_application_service),
    _: None = Depends(require_internal_key),
):
    """Issues a fresh key pair without revoking the current ones (no downtime)."""
    return await service.create_key(application_id)


@router.delete(
    "/{application_id}/keys/{key_id}",
    response_model=RevokeKeyResponse,
    status_code=status.HTTP_200_OK,
    summary="Revoke a key (immediate, no cache TTL wait)",
    operation_id="revoke_key",
    include_in_schema=False,
)
async def revoke_key(
    application_id: str,
    key_id: str,
    service: ApplicationService = Depends(get_application_service),
    _: None = Depends(require_internal_key),
):
    """Revokes a key and actively invalidates the resolution cache."""
    await service.revoke_key(application_id, key_id)
    return RevokeKeyResponse(message="Key revoked.")


@router.get(
    "/{application_id}",
    response_model=ApplicationResponse,
    status_code=status.HTTP_200_OK,
    summary="Get an application (admin)",
    operation_id="get_application",
    include_in_schema=False,
)
async def get_application(
    application_id: str,
    service: ApplicationService = Depends(get_application_service),
    _: None = Depends(require_internal_key),
):
    application = await service.get_application(application_id)
    if application is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found.",
        )
    return application


@router.patch(
    "/{application_id}",
    response_model=ApplicationResponse,
    status_code=status.HTTP_200_OK,
    summary="Update an application (admin)",
    operation_id="update_application",
    include_in_schema=False,
)
async def update_application(
    application_id: str,
    data: ApplicationUpdate,
    service: ApplicationService = Depends(get_application_service),
    _: None = Depends(require_internal_key),
):
    application = await service.update_application(application_id, data)
    if application is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found.",
        )
    return application
