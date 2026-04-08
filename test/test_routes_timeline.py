"""Tests for :mod:`src.routes.timeline`.

Covers the ``/timeline`` route (unauthenticated redirect, empty follow list,
populated follow list) and the ``_parse_day`` helper that converts stored
timestamps into display-friendly date strings.
"""

from __future__ import annotations

from unittest.mock import patch

from flask.testing import FlaskClient

from src.routes.timeline import _parse_day

# ===================================================================
# GET /timeline
# ===================================================================


class TestTimelineRoute:
    """Tests for the ``GET /timeline`` endpoint."""

    def test_timeline_unauthenticated_redirects(
        self, client: FlaskClient
    ) -> None:
        """GET /timeline when not logged in should redirect (302) to /login."""
        response = client.get("/timeline")

        assert response.status_code == 302
        assert "/login" in response.headers["Location"]

    def test_timeline_no_follows_returns_200(
        self, auth_client: FlaskClient
    ) -> None:
        """GET /timeline as an authenticated user with no follows should return 200."""
        response = auth_client.get("/timeline")

        assert response.status_code == 200

    @patch("src.routes.timeline.resolve_xbox_icon_fallbacks")
    def test_timeline_with_followed_achievements_returns_200(
        self,
        mock_resolve: object,
        auth_client: FlaskClient,
        db_session,
        make_user,
        make_user_follow,
        make_achievement,
        make_user_achievement,
    ) -> None:
        """GET /timeline with followed users who have achievements should return 200.

        ``resolve_xbox_icon_fallbacks`` is mocked to avoid external API calls.
        """
        auth_user = auth_client._user  # type: ignore[attr-defined]

        followed_user = make_user(
            username="followed",
            email="followed@example.com",
            password_hash="hash",
        )
        make_user_follow(follower=auth_user, followed=followed_user)

        achievement = make_achievement()
        make_user_achievement(
            user=followed_user,
            achievement=achievement,
            time_unlocked="2024-01-15T10:30:00Z",
        )
        db_session.commit()

        response = auth_client.get("/timeline")

        assert response.status_code == 200
        mock_resolve.assert_called_once()


# ===================================================================
# _parse_day helper
# ===================================================================


class TestParseDay:
    """Tests for the :func:`_parse_day` helper function."""

    def test_parse_day_none_returns_unknown(self) -> None:
        """``_parse_day(None)`` should return ``'Unknown date'``."""
        assert _parse_day(None) == "Unknown date"

    def test_parse_day_empty_returns_unknown(self) -> None:
        """``_parse_day('')`` should return ``'Unknown date'``."""
        assert _parse_day("") == "Unknown date"

    def test_parse_day_valid_iso_format(self) -> None:
        """A valid ISO-8601 timestamp should be formatted as 'Month DD, YYYY'."""
        assert _parse_day("2024-01-15T10:30:00Z") == "January 15, 2024"

    def test_parse_day_invalid_format_fallback(self) -> None:
        """An unparseable string of length >= 10 should return its first 10 characters."""
        assert _parse_day("not-a-date-at-all") == "not-a-date"

    def test_parse_day_short_string_fallback(self) -> None:
        """An unparseable string shorter than 10 chars should be returned as-is."""
        assert _parse_day("short") == "short"
