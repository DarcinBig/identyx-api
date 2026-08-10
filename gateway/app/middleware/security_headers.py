
"""
Security Headers Middleware — pure ASGI implementation.

We do NOT use BaseHTTPMiddleware here because it has compatibility
issues with streaming responses in certain versions of Starlette.
We implement the ASGI protocol directly.
"""

class SecurityHeadersMiddleware:
    """
    Adds HTTP security headers to every response.
    Pure ASGI implementation — compatible with all versions
    of Starlette and FastAPI.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_security_headers(message):
            if message["type"] == "http.response.start":
                headers = dict(message.get("headers", []))

                # Add security headers
                headers[b"x-content-type-options"] = b"nosniff"
                headers[b"x-frame-options"] = b"DENY"
                headers[b"x-xss-protection"] = b"1; mode=block"
                headers[b"referrer-policy"] = b"strict-origin-when-cross-origin"
                headers[b"permissions-policy"] = b"camera=(), microphone=(), geolocation=()"
                headers[b"strict-transport-security"] = b"max-age=31536000; includeSubDomains"

                # Remove the Server header
                headers.pop(b"server", None)

                message = {
                    **message,
                    "headers": list(headers.items()),
                }

            await send(message)

        await self.app(scope, receive, send_with_security_headers)