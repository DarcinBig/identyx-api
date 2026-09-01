"""Pydantic schemas for application-service.

Two concerns live here:
  - Admin/internal schemas (break-glass, plateforme) — used by the
    /applications/* admin endpoints, hidden from the public OpenAPI.
  - The public introspection schema for GET /v1/public/applications/me
    (exposed via the gateway) — only non-sensitive fields.

Never expose key_hash, webhook_secret_hash, or other keys' details.
"""

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

# ─── Admin / internal schemas ─────────────────────────────────────────


class ApplicationCreate(BaseModel):
    """Create an application + its first key pair (admin / break-glass)."""

    name: str = Field(min_length=1, max_length=255)
    owner_email: EmailStr
    allowed_origins: list[str] = Field(default_factory=list)
    webhook_url: str | None = None

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        return v.strip()


class ApplicationUpdate(BaseModel):
    """Partial update of an application (admin / break-glass)."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    allowed_origins: list[str] | None = None
    webhook_url: str | None = None
    status: str | None = Field(default=None, pattern="^(active|suspended)$")


class ApplicationResponse(BaseModel):
    """Admin view of an application (no key material)."""

    id: str
    tenant_id: str
    name: str
    owner_email: str
    allowed_origins: list[str]
    webhook_url: str | None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ApplicationCreatedResponse(BaseModel):
    """Returned by POST /applications — contains the ONLY display of the keys."""

    application_id: str
    tenant_id: str
    publishable_key: str
    secret_key: str

    model_config = {"from_attributes": True}


class ApplicationKeyCreatedResponse(BaseModel):
    """Returned by POST /applications/{id}/keys (rotation)."""

    application_id: str
    publishable_key: str
    secret_key: str


class ApiKeyInfo(BaseModel):
    """One API key row, safe for admin listing."""

    id: str
    key_id: str
    key_type: str
    environment: str
    status: str
    created_at: datetime
    revoked_at: datetime | None = None

    model_config = {"from_attributes": True}


class ApplicationKeysResponse(BaseModel):
    """All keys of an application (admin listing)."""

    application_id: str
    keys: list[ApiKeyInfo]


class ApplicationListResponse(BaseModel):
    """Paged listing of applications (admin)."""

    applications: list[ApplicationResponse]
    total: int


# ─── Key verification ─────────────────────────────────────────────────


class VerifyKeyRequest(BaseModel):
    """Internal: resolve a key into a tenant. Called by the gateway."""

    key_id: str
    secret: str


class VerifyKeyResult(BaseModel):
    tenant_id: str
    application_id: str
    key_type: str
    allowed_origins: list[str]
    status: str


class ResolveByOriginResult(BaseModel):
    """Result of an origin lookup for dynamic CORS (Sub-step D).

    `allowed` is True when the origin is registered by at least one active
    application. The gateway uses this at CORS preflight (no API key is
    presented for OPTIONS), then validates the key on the actual request.
    """

    allowed: bool
    applications: list[str]


# ─── Public introspection (via gateway) ───────────────────────────────


class PublicApplicationInfo(BaseModel):
    """Safe metadata for GET /v1/public/applications/me.

    Never key_hash, webhook_secret_hash, nor other keys' details.
    """

    application_id: str
    name: str
    allowed_origins: list[str]
    status: str
    key_type: str


class RevokeKeyResponse(BaseModel):
    message: str
