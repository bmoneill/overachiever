"""Tests for :mod:`src.api.api_request`.

Covers :func:`_build_cache_key` (cache-key construction) and
:func:`make_request` (caching behaviour, cache expiry, non-200
passthrough, and delegation to ``requests.request``).
"""

from __future__ import annotations

from typing import Generator
from unittest.mock import MagicMock, patch

import pytest
import requests

from src.api.api_request import (
    API_CACHE,
    API_CACHE_EXPIRY,
    TIMEOUT,
    _build_cache_key,
    make_request,
)

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _make_fake_response(
    status_code: int = 200,
    json_data: dict | None = None,
) -> MagicMock:
    """Build a mock :class:`requests.Response`."""
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    return resp


@pytest.fixture(autouse=True)
def _clear_cache() -> Generator:
    """Ensure the module-level ``API_CACHE`` is empty before and after each test."""
    API_CACHE.clear()
    yield
    API_CACHE.clear()


# ===================================================================
# _build_cache_key
# ===================================================================


class TestBuildCacheKey:
    """Tests for :func:`_build_cache_key`."""

    def test_url_only(self) -> None:
        """Key should incorporate the URL when no params are given."""
        key = _build_cache_key("https://example.com/api")
        assert "https://example.com/api" in key

    def test_with_params(self) -> None:
        """Key should incorporate both URL and params."""
        key = _build_cache_key("https://example.com/api", {"a": "1"})
        assert "https://example.com/api" in key
        assert "a" in key
        assert "1" in key

    def test_none_params(self) -> None:
        """Passing ``None`` explicitly should still produce a valid key."""
        key = _build_cache_key("https://example.com/api", None)
        assert isinstance(key, str)

    def test_different_params_produce_different_keys(self) -> None:
        """Different param dicts should yield different cache keys."""
        key_a = _build_cache_key("https://example.com", {"x": "1"})
        key_b = _build_cache_key("https://example.com", {"x": "2"})
        assert key_a != key_b

    def test_different_urls_produce_different_keys(self) -> None:
        """Different URLs with the same params should yield different keys."""
        key_a = _build_cache_key("https://a.com", {"x": "1"})
        key_b = _build_cache_key("https://b.com", {"x": "1"})
        assert key_a != key_b


# ===================================================================
# make_request — basic behaviour
# ===================================================================


class TestMakeRequestBasic:
    """Tests for :func:`make_request` basic / happy-path behaviour."""

    @patch("src.api.api_request.requests.request")
    def test_delegates_to_requests(self, mock_request: MagicMock) -> None:
        """Should call ``requests.request`` with the right arguments."""
        fake_resp = _make_fake_response(200)
        mock_request.return_value = fake_resp

        result = make_request(
            "https://api.example.com/data",
            method="GET",
            headers={"X-Token": "abc"},
            params={"q": "test"},
        )

        mock_request.assert_called_once_with(
            "GET",
            "https://api.example.com/data",
            headers={"X-Token": "abc"},
            params={"q": "test"},
            timeout=TIMEOUT,
        )
        assert result is fake_resp

    @patch("src.api.api_request.requests.request")
    def test_default_method_is_get(self, mock_request: MagicMock) -> None:
        """When no method is specified, default should be ``GET``."""
        mock_request.return_value = _make_fake_response(200)
        make_request("https://api.example.com")
        args, _kwargs = mock_request.call_args
        assert args[0] == "GET"

    @patch("src.api.api_request.requests.request")
    def test_returns_response_object(self, mock_request: MagicMock) -> None:
        """Should return the ``requests.Response`` from the underlying call."""
        fake_resp = _make_fake_response(200, {"ok": True})
        mock_request.return_value = fake_resp

        result = make_request("https://api.example.com")
        assert result.status_code == 200
        assert result.json() == {"ok": True}


# ===================================================================
# make_request — caching
# ===================================================================


class TestMakeRequestCaching:
    """Tests for the in-memory caching layer inside :func:`make_request`."""

    @patch("src.api.api_request.requests.request")
    def test_second_call_returns_cached(self, mock_request: MagicMock) -> None:
        """A second identical request should return the cached response
        without issuing another HTTP call."""
        fake_resp = _make_fake_response(200, {"cached": True})
        mock_request.return_value = fake_resp

        url = "https://api.example.com/cached"
        first = make_request(url, params={"a": "1"})
        second = make_request(url, params={"a": "1"})

        assert first is second
        assert mock_request.call_count == 1

    @patch("src.api.api_request.requests.request")
    def test_different_params_not_cached(self, mock_request: MagicMock) -> None:
        """Requests with different params should NOT share a cache entry."""
        fake_resp_a = _make_fake_response(200, {"v": "a"})
        fake_resp_b = _make_fake_response(200, {"v": "b"})
        mock_request.side_effect = [fake_resp_a, fake_resp_b]

        url = "https://api.example.com"
        first = make_request(url, params={"x": "1"})
        second = make_request(url, params={"x": "2"})

        assert mock_request.call_count == 2
        assert first is not second

    @patch("src.api.api_request.requests.request")
    def test_non_200_not_cached(self, mock_request: MagicMock) -> None:
        """Responses with non-200 status codes should not be cached."""
        bad_resp = _make_fake_response(500)
        ok_resp = _make_fake_response(200)
        mock_request.side_effect = [bad_resp, ok_resp]

        url = "https://api.example.com/fail"
        first = make_request(url)
        second = make_request(url)

        assert first.status_code == 500
        assert second.status_code == 200
        assert mock_request.call_count == 2

    @patch("src.api.api_request.requests.request")
    @patch("src.api.api_request.time.time")
    def test_cache_expiry(
        self, mock_time: MagicMock, mock_request: MagicMock
    ) -> None:
        """Cached entries older than ``API_CACHE_EXPIRY`` should be evicted."""
        resp_old = _make_fake_response(200, {"v": "old"})
        resp_new = _make_fake_response(200, {"v": "new"})
        mock_request.side_effect = [resp_old, resp_new]

        # First call at t=1000
        mock_time.return_value = 1000.0
        url = "https://api.example.com/expiry"
        make_request(url)
        assert mock_request.call_count == 1

        # Second call just before expiry — should still be cached
        mock_time.return_value = 1000.0 + API_CACHE_EXPIRY - 1
        make_request(url)
        assert mock_request.call_count == 1

        # Third call after expiry — should fetch again
        mock_time.return_value = 1000.0 + API_CACHE_EXPIRY + 1
        result = make_request(url)
        assert mock_request.call_count == 2
        assert result.json() == {"v": "new"}

    @patch("src.api.api_request.requests.request")
    def test_cache_stores_response(self, mock_request: MagicMock) -> None:
        """After a successful request, the cache should contain the entry."""
        fake_resp = _make_fake_response(200)
        mock_request.return_value = fake_resp

        url = "https://api.example.com/store"
        make_request(url)

        key = _build_cache_key(url, None)
        assert key in API_CACHE
        assert API_CACHE[key]["response"] is fake_resp
        assert "time" in API_CACHE[key]


# ===================================================================
# make_request — non-200 passthrough
# ===================================================================


class TestMakeRequestNon200:
    """Verify that non-200 responses are returned directly (not raised)."""

    @patch("src.api.api_request.requests.request")
    def test_returns_404(self, mock_request: MagicMock) -> None:
        """A 404 should be returned as-is, not raise."""
        mock_request.return_value = _make_fake_response(404)
        result = make_request("https://api.example.com/missing")
        assert result.status_code == 404

    @patch("src.api.api_request.requests.request")
    def test_returns_500(self, mock_request: MagicMock) -> None:
        """A 500 should be returned as-is, not raise."""
        mock_request.return_value = _make_fake_response(500)
        result = make_request("https://api.example.com/error")
        assert result.status_code == 500

    @patch("src.api.api_request.requests.request")
    def test_returns_403(self, mock_request: MagicMock) -> None:
        """A 403 should be returned as-is, not raise."""
        mock_request.return_value = _make_fake_response(403)
        result = make_request("https://api.example.com/forbidden")
        assert result.status_code == 403
