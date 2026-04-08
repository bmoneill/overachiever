"""Tests for :mod:`src.routes.all_games`.

Covers the two public endpoints exposed by the all-games route module:

* ``GET /games`` – lists every title in the database.
* ``GET /games/<int:title_id>`` – shows achievements for a single title.
"""

from __future__ import annotations

from unittest.mock import patch

from flask.testing import FlaskClient

# ===================================================================
# GET /games
# ===================================================================


class TestAllGames:
    """Tests for the ``GET /games`` endpoint."""

    def test_all_games_empty_returns_200(self, client: FlaskClient) -> None:
        """An empty database should still yield a 200 response."""
        response = client.get("/games")

        assert response.status_code == 200

    def test_all_games_with_titles_returns_200(
        self,
        client: FlaskClient,
        make_title,
        make_achievement,
        db_session,
    ) -> None:
        """When titles exist the page should return 200 and contain their names."""
        make_title(name="Halo Infinite", platform=1, platform_title_id="100")
        steam_title = make_title(
            name="Portal 2", platform=2, platform_title_id="200"
        )
        # The template hides Steam titles with zero achievements, so we
        # create one to ensure Portal 2 is rendered.
        make_achievement(title=steam_title)
        db_session.commit()

        response = client.get("/games")

        assert response.status_code == 200
        assert b"Halo Infinite" in response.data
        assert b"Portal 2" in response.data


# ===================================================================
# GET /games/<int:title_id>
# ===================================================================


class TestAllGameAchievements:
    """Tests for the ``GET /games/<int:title_id>`` endpoint."""

    @patch("src.routes.all_games.resolve_xbox_icon_fallbacks")
    def test_all_game_achievements_existing_returns_200(
        self,
        mock_resolve: object,
        client: FlaskClient,
        make_title,
        db_session,
    ) -> None:
        """A valid title id should return 200."""
        title = make_title(
            name="Halo Infinite",
            platform=1,
            platform_title_id="100",
        )
        db_session.commit()

        response = client.get(f"/games/{title.id}")

        assert response.status_code == 200

    def test_all_game_achievements_nonexistent_redirects(
        self,
        client: FlaskClient,
    ) -> None:
        """A nonexistent title id should redirect to ``/games``."""
        response = client.get("/games/999")

        assert response.status_code == 302
        assert response.headers["Location"].endswith("/games")

    @patch("src.routes.all_games.resolve_xbox_icon_fallbacks")
    def test_all_game_achievements_with_achievements(
        self,
        mock_resolve: object,
        client: FlaskClient,
        make_title,
        make_achievement,
        db_session,
    ) -> None:
        """Achievements associated with the title should appear in the response."""
        title = make_title(
            name="Halo Infinite",
            platform=1,
            platform_title_id="100",
        )
        make_achievement(
            title=title,
            achievement_name="First Strike",
        )
        make_achievement(
            title=title,
            achievement_name="Completionist",
        )
        db_session.commit()

        response = client.get(f"/games/{title.id}")

        assert response.status_code == 200
        assert b"First Strike" in response.data
        assert b"Completionist" in response.data
