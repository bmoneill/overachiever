"""Tests for :mod:`src.helpers.image_cache`.

Verifies that:
- The cache filename is derived from a stable, process-restart-proof hash.
- Already-cached files are not re-fetched over the network.
- Missing files are downloaded, written to disk, and the socket notification
  is sent exactly once.
- The cache directory is created automatically when absent.

All filesystem I/O, network calls, and socket operations are mocked so that
no real side-effects occur during the test run.

Note: The module-level ``autouse`` ``mock_image_cache`` fixture in
``conftest.py`` patches *references* to ``get_image_path`` in other modules.
The tests here import the function directly, so they always exercise the real
implementation despite that fixture being active.
"""

from __future__ import annotations

import hashlib
import socket
from unittest.mock import MagicMock, mock_open, patch

import pytest
from flask import Flask

from src.helpers.image_cache import IMAGE_CACHE_DIR, get_image_path

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TEST_URL = "https://cdn.example.com/games/440/header.jpg"
_EXPECTED_HASH = hashlib.sha256(_TEST_URL.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestGetImagePathHashStability:
    """The filename component must be stable across process restarts."""

    def test_hash_is_sha256_of_url(self, app: Flask) -> None:
        """Returned path must end with the SHA-256 hex digest of the URL.

        This directly guards against regression to Python's built-in
        ``hash()``, which is randomised per-process and would cause every
        server restart to generate a different filename.
        """
        with app.test_request_context("/"):
            with patch("os.path.exists", return_value=True):
                path = get_image_path(_TEST_URL)

        assert path.endswith(_EXPECTED_HASH), (
            f"Expected path to end with SHA-256 digest '{_EXPECTED_HASH}', "
            f"got '{path}'"
        )

    def test_same_url_always_returns_same_path(self, app: Flask) -> None:
        """Calling get_image_path twice with the same URL returns the same path."""
        with app.test_request_context("/"):
            with patch("os.path.exists", return_value=True):
                path_a = get_image_path(_TEST_URL)
                path_b = get_image_path(_TEST_URL)

        assert path_a == path_b

    def test_different_urls_return_different_paths(self, app: Flask) -> None:
        """Different URLs must map to different local paths."""
        url_a = "https://cdn.example.com/icon_a.jpg"
        url_b = "https://cdn.example.com/icon_b.jpg"

        with app.test_request_context("/"):
            with patch("os.path.exists", return_value=True):
                path_a = get_image_path(url_a)
                path_b = get_image_path(url_b)

        assert path_a != path_b


class TestGetImagePathCacheHit:
    """When the cached file already exists no network call is made."""

    def test_no_http_request_when_file_cached(self, app: Flask) -> None:
        """``requests.get`` must not be called if the image file exists on disk."""
        with app.test_request_context("/"):
            with (
                patch("os.path.exists", return_value=True),
                patch("requests.get") as mock_get,
            ):
                get_image_path(_TEST_URL)

        mock_get.assert_not_called()

    def test_no_socket_notification_when_file_cached(self, app: Flask) -> None:
        """The socket notification must not be sent for a cache hit."""
        mock_socket = MagicMock(spec=socket.socket)

        with app.test_request_context("/"):
            with (
                patch("os.path.exists", return_value=True),
                patch("socket.socket", return_value=mock_socket),
            ):
                get_image_path(_TEST_URL)

        mock_socket.connect.assert_not_called()


class TestGetImagePathCacheMiss:
    """When the cached file is absent the image is downloaded and saved."""

    def _make_mock_response(self, chunks: list[bytes]) -> MagicMock:
        """Return a mock requests.Response whose iter_content yields *chunks*."""
        resp = MagicMock()
        resp.iter_content.return_value = iter(chunks)
        return resp

    def test_image_is_downloaded_on_miss(self, app: Flask) -> None:
        """``requests.get`` is called once with the original URL when the file is missing."""
        mock_response = self._make_mock_response([b"img_data"])
        mock_sock = MagicMock(spec=socket.socket)

        # os.path.exists: first call is for IMAGE_CACHE_DIR (True),
        # second is for the target file (False → cache miss).
        with app.test_request_context("/"):
            with (
                patch("os.path.exists", side_effect=[True, False]),
                patch("requests.get", return_value=mock_response) as mock_get,
                patch("builtins.open", mock_open()),
                patch("socket.socket", return_value=mock_sock),
            ):
                get_image_path(_TEST_URL)

        mock_get.assert_called_once_with(_TEST_URL, stream=True, timeout=10)

    def test_image_bytes_written_to_file(self, app: Flask) -> None:
        """Downloaded bytes are written to the target file."""
        mock_response = self._make_mock_response([b"chunk1", b"chunk2"])
        mock_sock = MagicMock(spec=socket.socket)
        m = mock_open()

        with app.test_request_context("/"):
            with (
                patch("os.path.exists", side_effect=[True, False]),
                patch("requests.get", return_value=mock_response),
                patch("builtins.open", m),
                patch("socket.socket", return_value=mock_sock),
            ):
                get_image_path(_TEST_URL)

        handle = m()
        written = b"".join(call.args[0] for call in handle.write.call_args_list)
        assert written == b"chunk1chunk2"

    def test_socket_notification_sent_on_miss(self, app: Flask) -> None:
        """A socket notification is sent to localhost:9800 after a new download."""
        mock_response = self._make_mock_response([b"img_data"])
        mock_sock = MagicMock(spec=socket.socket)

        with app.test_request_context("/"):
            with (
                patch("os.path.exists", side_effect=[True, False]),
                patch("requests.get", return_value=mock_response),
                patch("builtins.open", mock_open()),
                patch("socket.socket", return_value=mock_sock),
            ):
                get_image_path(_TEST_URL)

        mock_sock.connect.assert_called_once_with(("localhost", 9800))
        mock_sock.sendall.assert_called_once()
        notification = mock_sock.sendall.call_args[0][0]
        assert _EXPECTED_HASH.encode() in notification

    def test_cache_dir_created_when_absent(self, app: Flask) -> None:
        """``os.makedirs`` is called when the cache directory does not exist."""
        mock_response = self._make_mock_response([b"img_data"])
        mock_sock = MagicMock(spec=socket.socket)

        # Both exists checks return False: directory missing, then file missing.
        with app.test_request_context("/"):
            with (
                patch("os.path.exists", return_value=False),
                patch("os.makedirs") as mock_makedirs,
                patch("requests.get", return_value=mock_response),
                patch("builtins.open", mock_open()),
                patch("socket.socket", return_value=mock_sock),
            ):
                get_image_path(_TEST_URL)

        mock_makedirs.assert_called_once_with(IMAGE_CACHE_DIR)
