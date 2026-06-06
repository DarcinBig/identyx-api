from fastapi import Request, HTTPException, status

def get_current_user_id(request: Request) -> str:
    """
    Extracts the logged-in user's ID from the X-User-Id header.
    Injected by the gateway after JWT validation.
    """
    user_id = request.headers.get("X-User-Id", "").strip()
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WW-Authenticate": "Bearer"},
        )
    return user_id