"""Unit tests for the email-service IP geolocation logic."""

from unittest.mock import patch

import pytest

from app.services.ip_geolocation import (
    _CACHE_TTL_SECONDS,
    _cache,
    _is_local_ip,
    resolve_location,
)


@pytest.fixture(autouse=True)
def clear_cache():
    _cache.clear()
    yield
    _cache.clear()


class TestIsLocalIp:
    def test_loopback(self):
        assert _is_local_ip("127.0.0.1")
        assert _is_local_ip("::1")

    def test_private(self):
        assert _is_local_ip("10.0.0.1")
        assert _is_local_ip("192.168.1.1")
        assert _is_local_ip("172.17.0.2")

    def test_public_ip(self):
        assert not _is_local_ip("8.8.8.8")
        assert not _is_local_ip("1.1.1.1")

    def test_garbage(self):
        assert _is_local_ip("not-an-ip")


class TestResolveLocation:
    @pytest.mark.asyncio
    async def test_empty_ip(self):
        assert await resolve_location("") == "Unknown location"
        assert await resolve_location(None) == "Unknown location"

    @pytest.mark.asyncio
    async def test_local_ip_short_circuits(self):
        with patch("app.services.ip_geolocation._api_lookup") as lookup:
            assert await resolve_location("10.0.0.5") == "Local network"
            lookup.assert_not_called()

    @pytest.mark.asyncio
    async def test_api_lookup_success(self):
        with patch("app.services.ip_geolocation._api_lookup", return_value="Paris, Île-de-France, France"):
            assert await resolve_location("8.8.8.8") == "Paris, Île-de-France, France"

    @pytest.mark.asyncio
    async def test_api_lookup_failure_graceful(self):
        with patch("app.services.ip_geolocation._api_lookup", side_effect=RuntimeError("boom")):
            assert await resolve_location("8.8.8.8") == "Unknown location"

    @pytest.mark.asyncio
    async def test_empty_result_becomes_unknown(self):
        with patch("app.services.ip_geolocation._api_lookup", return_value=""):
            assert await resolve_location("8.8.8.8") == "Unknown location"

    @pytest.mark.asyncio
    async def test_cache_avoids_second_lookup(self):
        with patch("app.services.ip_geolocation._api_lookup", return_value="Paris, France") as lookup:
            assert await resolve_location("8.8.8.8") == "Paris, France"
            assert await resolve_location("8.8.8.8") == "Paris, France"
            assert lookup.call_count == 1

    @pytest.mark.asyncio
    async def test_ttl_expiry_triggers_second_lookup(self):
        with patch("app.services.ip_geolocation._api_lookup", return_value="Paris, France") as lookup:
            assert await resolve_location("8.8.8.8") == "Paris, France"
            # Simulate the cache entry expiring
            cached = _cache["8.8.8.8"]
            _cache["8.8.8.8"] = (cached[0] - _CACHE_TTL_SECONDS - 1, cached[1])
            assert await resolve_location("8.8.8.8") == "Paris, France"
            assert lookup.call_count == 2
