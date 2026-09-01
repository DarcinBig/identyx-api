"""
ApplicationService — orchestration for applications and their API keys.

Responsibilities:
  - create_application : creates an app + first key pair (publishable/secret)
  - verify_key          : resolves a key into {tenant_id, ...} using the cache
                          first (Redis DB 3), then the DB; cache-on-success.
  - create_key          : rotation — issues a NEW pair, keeps the old ones active
  - revoke_key          : soft-revoke + active cache invalidation (no TTL wait)

Correctness rule: the service must stay correct even with the cache disabled
or down — the cache is an accelerator, not a functional dependency.
"""

import logging

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.redis import (
    get_cached_resolution,
    invalidate_key,
    set_cached_resolution,
)
from app.models.api_key import ApiKey
from app.models.application import Application
from app.repositories.api_key_repo import ApiKeyRepository
from app.repositories.application_repo import ApplicationRepository
from app.schemas.application import (
    ApplicationCreate,
    ApplicationCreatedResponse,
    ApplicationKeyCreatedResponse,
    ApplicationUpdate,
    PublicApplicationInfo,
    ResolveByOriginResult,
    VerifyKeyResult,
)
from app.security.key_generation import (
    KeyPair,
    generate_key_pair,
    get_key_id,
    hash_api_key,
    verify_api_key,
)

logger = logging.getLogger("application-service")


class ApplicationService:
    def __init__(
        self,
        db: AsyncSession,
        cache_client=None,
    ):
        self.db = db
        self.application_repo = ApplicationRepository(db)
        self.api_key_repo = ApiKeyRepository(db)
        # cache_client is kept for dependency injection in tests; the cache
        # helpers below already route to the shared client.
        self.cache_client = cache_client
        # Set by _issue_key_pair — holds the pair that must be shown exactly once.
        self._last_issued_pair: KeyPair | None = None

    # ─── Creation ────────────────────────────────────────────────────

    async def create_application(self, data: ApplicationCreate) -> ApplicationCreatedResponse:
        await self._ensure_origins_available(list(data.allowed_origins), exclude_app_id=None)
        application = await self.application_repo.create(data)
        await self._issue_key_pair(application.id)
        await self.db.commit()

        # The full keys must be shown exactly once — right here.
        pair = self._last_issued_pair
        logger.info(
            "application_created",
            extra={"application_id": application.id, "tenant_id": application.tenant_id},
        )
        return ApplicationCreatedResponse(
            application_id=application.id,
            tenant_id=application.tenant_id,
            publishable_key=pair.publishable,
            secret_key=pair.secret,
        )

    async def _ensure_origins_available(
        self, origins: list[str], exclude_app_id: str | None
    ) -> None:
        """Cross-app origin uniqueness.

        Each origin may be claimed by at most one application. If any requested
        origin is already registered by another application, raise 409 so the
        caller can't silently override another app's CORS policy.
        """
        origins = [o for o in origins if o]
        if not origins:
            return

        conflicts = await self.application_repo.find_active_by_origins(origins)
        for app in conflicts:
            if app.id != exclude_app_id:
                claimed = [o for o in origins if o in (app.allowed_origins or [])]
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"Origin(s) already claimed by another application: "
                        f"{', '.join(claimed)}."
                    ),
                )

    async def _issue_key_pair(self, application_id: str) -> None:
        pair = generate_key_pair()
        for full_key, key_type in (
            (pair.publishable, "publishable"),
            (pair.secret, "secret"),
        ):
            await self.api_key_repo.create(
                application_id=application_id,
                key_id=get_key_id(full_key),
                key_hash=hash_api_key(full_key),
                key_type=key_type,
            )
        self._last_issued_pair = pair

    # ─── Rotation ────────────────────────────────────────────────────

    async def create_key(self, application_id: str) -> ApplicationKeyCreatedResponse:
        application = await self.application_repo.get_by_id(application_id)
        if application is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Application not found.",
            )
        if application.status == "suspended":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Application is suspended.",
            )

        await self._issue_key_pair(application_id)
        await self.db.commit()

        # Rotation keeps existing keys active — no downtime for the app.
        pair = self._last_issued_pair
        logger.info(
            "application_key_rotated",
            extra={"application_id": application_id},
        )
        return ApplicationKeyCreatedResponse(
            application_id=application_id,
            publishable_key=pair.publishable,
            secret_key=pair.secret,
        )

    # ─── Revocation ──────────────────────────────────────────────────

    async def revoke_key(self, application_id: str, key_id: str) -> None:
        application = await self.application_repo.get_by_id(application_id)
        if application is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Application not found.",
            )

        key = await self.api_key_repo.get_by_key_id(key_id)
        if key is None or key.application_id != application_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Key not found.",
            )

        await self.api_key_repo.revoke(key_id)
        await self.db.commit()

        # Active invalidation — the revoked key dies immediately, no TTL wait.
        await invalidate_key(key_id)
        logger.info(
            "application_key_revoked",
            extra={"application_id": application_id, "key_id": key_id},
        )

    # ─── Verification (the hot path) ─────────────────────────────────

    async def verify_key(self, full_key: str, secret: str) -> VerifyKeyResult | None:
        """
        Resolves a key into its application context.

        Returns None when:
          - the key does not exist,
          - the secret does not match,
          - the key is revoked,
          - the application is suspended (even with an active key).

        Cache-first (Redis DB 3), DB on miss, cache-on-success.
        """
        key_id = get_key_id(full_key)

        # 1. Cache fast path
        cached = await get_cached_resolution(key_id)
        if cached is not None and cached.get("key_hash") is not None:
            if cached.get("status") != "active":
                return None
            # The secret must be re-validated even on a cache hit: the cache
            # is keyed by key_id only, so it must not turn into a pass for
            # any wrong secret sharing the same key_id. Fall through to the
            # DB path for stale entries that carry no hash.
            if not verify_api_key(secret, cached["key_hash"], key_id=key_id):
                return None
            return VerifyKeyResult(
                tenant_id=cached["tenant_id"],
                application_id=cached["application_id"],
                key_type=cached["key_type"],
                allowed_origins=cached.get("allowed_origins", []),
                status=cached["status"],
            )

        # 2. DB path
        key: ApiKey | None = await self.api_key_repo.get_by_key_id(key_id)
        if key is None or key.status != "active":
            return None
        if not verify_api_key(secret, key.key_hash, key_id=key_id):
            return None

        application: Application | None = await self.application_repo.get_by_id(key.application_id)
        if application is None or application.status != "active":
            return None

        result = VerifyKeyResult(
            tenant_id=application.tenant_id,
            application_id=application.id,
            key_type=key.key_type,
            allowed_origins=list(application.allowed_origins),
            status=application.status,
        )

        # 3. Cache-on-success (errors non-fatal)
        await set_cached_resolution(
            key_id,
            {
                "tenant_id": result.tenant_id,
                "application_id": result.application_id,
                "key_type": result.key_type,
                "allowed_origins": result.allowed_origins,
                "status": result.status,
                "key_hash": key.key_hash,
            },
        )
        return result

    # ─── Public introspection (GET /applications/me) ─────────────────

    async def introspect_key(self, full_key: str) -> PublicApplicationInfo | None:
        """
        Resolves the presented key and returns only non-sensitive application
        metadata: application_id, name, allowed_origins, status, key_type.

        Never returns key_hash, webhook_secret_hash, or other keys' details.
        Returns None for unknown/revoked keys or suspended applications.
        """
        result = await self.verify_key(full_key, full_key)
        if result is None:
            return None
        application = await self.application_repo.get_by_id(result.application_id)
        if application is None:
            return None
        return PublicApplicationInfo(
            application_id=application.id,
            name=application.name,
            allowed_origins=result.allowed_origins,
            status=application.status,
            key_type=result.key_type,
        )

    # ─── Dynamic CORS resolution (resolve-by-origin) ─────────────────

    async def resolve_by_origin(self, origin: str) -> ResolveByOriginResult:
        """Resolve whether any active application allows the given origin.

        Used by the gateway during CORS preflight, where no API key is
        presented (browsers don't send X-Identyx-Key on OPTIONS). The origin
        is matched against each active application's `allowed_origins` via the
        GIN index; the key is only validated on the actual request.
        """
        origin = (origin or "").strip().rstrip("/")
        if not origin:
            return ResolveByOriginResult(allowed=False, applications=[])

        matching = await self.application_repo.find_active_by_origins([origin])
        return ResolveByOriginResult(
            allowed=bool(matching),
            applications=[app.id for app in matching],
        )

    # ─── Read / update helpers (admin) ───────────────────────────────

    async def get_application(self, application_id: str) -> Application | None:
        return await self.application_repo.get_by_id(application_id)

    async def update_application(
        self, application_id: str, data: ApplicationUpdate
    ) -> Application | None:
        application = await self.application_repo.get_by_id(application_id)
        if application is None:
            return None
        if data.allowed_origins is not None:
            await self._ensure_origins_available(
                list(data.allowed_origins), exclude_app_id=application_id
            )
        application = await self.application_repo.update(application_id, data)
        if application is None:
            return None
        await self.db.commit()
        return application
