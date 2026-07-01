"""
FastAPI dependencies for the auth service.

`get_current_user_id()` reads the X-User-Id header
injected by the gateway after JWT validation.

Services never validate the JWT themselves —
that's the exclusive role of the gateway and token service.
"""
from fastapi import HTTPException, Request, status


def get_current_user_id(request: Request) -> str:
    """
    Extracts the logged-in user's ID from the X-User-Id header.

    This header is injected by the gateway after JWT validation.
    If absent → 401 (request not passed through the gateway or invalid token).

    Usage in a route:
        @router.post("/logout")
        async def logout(
        user_id: str = Depends(get_current_user_id),
        ...
        ):
    """
    user_id = request.headers.get("X-User-Id", "").strip()
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user_id
