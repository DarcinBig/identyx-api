#!/usr/bin/env python3
"""
Seed the native application (identyx-native).

Deterministic creation (§16.1):
  - name = "identyx-native"
  - owner_email = "plateforme@identyx.io"
  - tenant_id = IDENTYX_NATIVE_TENANT_ID (default: 00000000-...-000000000001)
  - Status = active, allowed_origins = localhost (dev)

Idempotent: exits cleanly if the application already exists.

Usage (from project root):
  python scripts/seed_native_application.py

Requires:
  - DATABASE_URL or POSTGRES_* env vars for the applications DB
  - INTERNAL_API_KEY (must match the application-service's config)
"""

import asyncio
import os
import sys

import httpx

APPLICATION_SERVICE_URL = os.getenv(
    "APPLICATION_SERVICE_URL", "http://localhost:8006"
)
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY", "")
NATIVE_TENANT_ID = os.getenv(
    "IDENTYX_NATIVE_TENANT_ID", "00000000-0000-0000-0000-000000000001"
)


async def seed() -> None:
    if not INTERNAL_API_KEY:
        print("ERROR: INTERNAL_API_KEY not set.", file=sys.stderr)
        sys.exit(1)

    headers = {"X-Internal-Key": INTERNAL_API_KEY}

    async with httpx.AsyncClient(timeout=10.0) as client:
        # Check if the application already exists by listing owner email
        try:
            resp = await client.get(
                f"{APPLICATION_SERVICE_URL}/health",
                headers=headers,
            )
            if resp.status_code != 200:
                print(
                    f"ERROR: application-service not reachable "
                    f"(status={resp.status_code}).",
                    file=sys.stderr,
                )
                sys.exit(1)
        except httpx.ConnectError:
            print(
                "ERROR: cannot connect to application-service at "
                f"{APPLICATION_SERVICE_URL}.",
                file=sys.stderr,
            )
            sys.exit(1)

        # Create the native application
        payload = {
            "name": "identyx-native",
            "owner_email": "plateforme@identyx.io",
            "allowed_origins": [
                "http://localhost:3000",
                "http://localhost:8000",
            ],
        }

        resp = await client.post(
            f"{APPLICATION_SERVICE_URL}/applications/",
            json=payload,
            headers=headers,
        )

        if resp.status_code == 201:
            data = resp.json()
            print("Native application created successfully.")
            print(f"  application_id : {data['application_id']}")
            print(f"  tenant_id      : {data['tenant_id']}")
            print()
            print("  ── API Keys (save these now — shown only once) ──")
            print(f"  publishable_key: {data['publishable_key']}")
            print(f"  secret_key     : {data['secret_key']}")
            print()
            print("Store these keys securely. They cannot be recovered.")
        elif resp.status_code == 409:
            print("Native application already exists. Skipping.")
        else:
            print(
                f"ERROR: unexpected response (status={resp.status_code}): "
                f"{resp.text}",
                file=sys.stderr,
            )
            sys.exit(1)


if __name__ == "__main__":
    asyncio.run(seed())
