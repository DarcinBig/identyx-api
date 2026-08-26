"""
ip_geolocation.py — Resolves an IP address to a human-readable location.

Used by the email-service to display "Paris, France"-style locations
in the new-login security notification (like other platforms do).

Implementation notes:
    - Free tier of ip-api.com (HTTP, no API key required).
    - Results are cached in memory per IP to respect the rate limit.
    - Private / reserved IPs are labeled "Local network" (no API call).
    - Any failure degrades gracefully to "Unknown location".
"""
import asyncio
import ipaddress
import json
import logging
import time
import urllib.request

logger = logging.getLogger("email-service.geoip")

# In-memory cache: ip -> (monotonic timestamp, location)
_cache: dict[str, tuple[float, str]] = {}
_CACHE_TTL_SECONDS = 3600


def _is_local_ip(ip: str) -> bool:
    """
    True for private, loopback, link-local, reserved or
    otherwise non-routable IPs (Docker networks, localhost, ...).
    """
    try:
        parsed = ipaddress.ip_address(ip.strip())
    except ValueError:
        return True
    return (
        parsed.is_private
        or parsed.is_loopback
        or parsed.is_link_local
        or parsed.is_reserved
        or parsed.is_multicast
        or parsed.is_unspecified
    )


def _api_lookup(ip: str) -> str:
    """
    Synchronous geolocation lookup — runs in a worker thread.
    Returns an empty string on any failure.
    """
    url = f"http://ip-api.com/json/{ip}?fields=status,country,regionName,city"
    request = urllib.request.Request(url, headers={"User-Agent": "Identyx/1.1.2"})
    with urllib.request.urlopen(request, timeout=5) as response:
        data = json.loads(response.read().decode("utf-8"))
    if data.get("status") != "success":
        return ""
    parts = [data.get("city"), data.get("regionName"), data.get("country")]
    return ", ".join(part for part in parts if part)


async def resolve_location(ip: str) -> str:
    """
    Resolves an IP to a location string ("Paris, France").
    Falls back to "Local network" / "Unknown location".
    """
    ip = (ip or "").strip()
    if not ip:
        return "Unknown location"

    if _is_local_ip(ip):
        return "Local network"

    now = time.monotonic()
    cached = _cache.get(ip)
    if cached and now - cached[0] < _CACHE_TTL_SECONDS:
        return cached[1]

    try:
        location = await asyncio.to_thread(_api_lookup, ip)
    except Exception as exc:
        logger.warning("geoip_lookup_failed", extra={"ip": ip, "error": str(exc)})
        location = ""

    if not location:
        location = "Unknown location"

    _cache[ip] = (now, location)
    return location
