"""Tests for the ``/my-games`` route (:mod:`src.routes.my_games`).

Covers authenticated redirection to the user's games page and
unauthenticated redirection to the login page.
"""

from __future__ import annotations

from flask.testing import FlaskClient


class TestMyGamesRoute:
    """Tests for ``GET /my-games``."""

    def test_my_games_authenticated_redirects_to_user_games(
        self, auth_client: FlaskClient
    ) -> None:
        """An authenticated user should be redirected to ``/games/<username>``."""
        response = auth_client.get("/my-games")

        assert response.status_code == 302
        assert response.headers["Location"].endswith("/games/testuser")

    def test_my_games_unauthenticated_redirects_to_login(
        self, client: FlaskClient
    ) -> None:
        """An unauthenticated visitor should be redirected to the login page."""
        response = client.get("/my-games")

        assert response.status_code == 302
        assert "/login" in response.headers["Location"]
