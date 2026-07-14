"""Tests for the fetch_url_metadata function in src.routes.games.

This module tests URL metadata extraction from various sources,
particularly Steam Community URLs.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def steam_guide_response():
    """Mock HTML response from a Steam Community Guide page."""
    return """
    <html>
        <head>
            <title>Steam Community :: Guide :: ARK: SURVIVAL ALL ACHIEVEMENTS (FAST)</title>
            <meta property="og:title" content="Steam Community :: Guide :: ARK: SURVIVAL ALL ACHIEVEMENTS (FAST)">
            <meta property="og:description" content="Probably one of the fastest guides to get all achievements in the game on ASA.&#10;&#10;The Cmds will be within &quot; &quot; I have separated them out so you can be a bit more lazy with the copy and paste,">
            <meta property="og:type" content="website">
        </head>
        <body>
            <h1>Guide content here</h1>
        </body>
    </html>
    """


class TestFetchUrlMetadata:
    """Tests for the fetch_url_metadata function."""

    def test_fetch_url_metadata_with_og_tags(self, steam_guide_response, app):
        """Test extracting metadata when og:title and og:description are present."""
        with app.app_context():
            from src.routes.games import fetch_url_metadata

            mock_response = MagicMock()
            mock_response.text = steam_guide_response
            mock_response.status_code = 200

            with patch(
                "src.routes.games.requests.get", return_value=mock_response
            ):
                title, description = fetch_url_metadata(
                    "http://steamcommunity.com/sharedfiles/filedetails/?id=3261584799"
                )

            assert title is not None
            assert "ARK: SURVIVAL ALL ACHIEVEMENTS" in title
            assert description is not None
            assert "fastest guides" in description

    def test_fetch_url_metadata_fallback_to_title_tag(self, app):
        """Test fallback to <title> tag when og:title is missing."""
        with app.app_context():
            from src.routes.games import fetch_url_metadata

            html_response = """
            <html>
                <head>
                    <title>My Awesome Guide</title>
                </head>
            </html>
            """
            mock_response = MagicMock()
            mock_response.text = html_response
            mock_response.status_code = 200

            with patch(
                "src.routes.games.requests.get", return_value=mock_response
            ):
                title, description = fetch_url_metadata(
                    "http://example.com/guide"
                )

            assert title == "My Awesome Guide"
            assert description is None

    def test_fetch_url_metadata_fallback_to_meta_description(self, app):
        """Test fallback to meta[name='description'] when og:description is missing."""
        with app.app_context():
            from src.routes.games import fetch_url_metadata

            html_response = """
            <html>
                <head>
                    <title>My Guide</title>
                    <meta name="description" content="This is a guide description">
                </head>
            </html>
            """
            mock_response = MagicMock()
            mock_response.text = html_response
            mock_response.status_code = 200

            with patch(
                "src.routes.games.requests.get", return_value=mock_response
            ):
                title, description = fetch_url_metadata(
                    "http://example.com/guide"
                )

            assert title == "My Guide"
            assert description == "This is a guide description"

    def test_fetch_url_metadata_returns_none_on_exception(self, app):
        """Test that the function returns (None, None) on exception."""
        with app.app_context():
            from src.routes.games import fetch_url_metadata

            with patch(
                "src.routes.games.requests.get",
                side_effect=Exception("Connection error"),
            ):
                title, description = fetch_url_metadata(
                    "http://example.com/guide"
                )

            assert title is None
            assert description is None

    def test_fetch_url_metadata_handles_timeout(self, app):
        """Test that the function handles timeout exceptions gracefully."""
        with app.app_context():
            from src.routes.games import fetch_url_metadata

            with patch(
                "src.routes.games.requests.get",
                side_effect=TimeoutError("Timeout"),
            ):
                title, description = fetch_url_metadata(
                    "http://example.com/guide"
                )

            assert title is None
            assert description is None
