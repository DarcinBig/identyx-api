"""
HTTP client shared between all routers on the gateway.
Initialized in lifespan (main.py), accessible everywhere via this module.
"""
import httpx

# Global variable — initialized in lifespan
client: httpx.AsyncClient | None = None