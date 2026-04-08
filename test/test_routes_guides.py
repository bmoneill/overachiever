"""Tests for :mod:`src.routes.guides`.

Covers the public guides index (``/guides``) and the per-game guides
page (``/guides/<platform>/<title_id>``), including empty-state
rendering and invalid-platform handling.
"""

from __future__ import annotations

from flask.testing import FlaskClient


class TestPublicGuidesIndex:
    """Tests for the ``GET /guides`` endpoint."""

    def test_guides_index_empty_returns_200(self, client: FlaskClient) -> None:
        """An empty database should still render the guides index with 200."""
        response = client.get("/guides")

        assert response.status_code == 200

    def test_guides_index_with_guides_returns_200(
        self,
        client: FlaskClient,
        db_session,
        make_title,
        make_user,
        make_achievement,
        make_guide,
    ) -> None:
        """The guides index should return 200 when guides exist.

        Creates a title and a guide whose ``platform_id`` and
        ``title_id`` match the title's ``platform`` and
        ``platform_title_id`` so that the route's
        ``Title.find_by_platform`` lookup succeeds.
        """
        title = make_title(platform=1, platform_title_id="200")
        achievement = make_achievement(title=title)
        user = make_user()
        make_guide(
            user=user,
            achievement=achievement,
            platform_id=title.platform,
            title_id=title.platform_title_id,
        )
        db_session.commit()

        response = client.get("/guides")

        assert response.status_code == 200
        assert title.name.encode() in response.data


class TestPublicGameGuides:
    """Tests for the ``GET /guides/<platform>/<title_id>`` endpoint."""

    def test_game_guides_returns_200(
        self,
        client: FlaskClient,
        db_session,
        make_title,
        make_user,
        make_achievement,
        make_guide,
    ) -> None:
        """A valid platform and title_id should render the game guides page."""
        title = make_title(platform=1, platform_title_id="300")
        achievement = make_achievement(title=title)
        user = make_user()
        make_guide(
            user=user,
            achievement=achievement,
            platform_id=title.platform,
            title_id=title.platform_title_id,
        )
        db_session.commit()

        response = client.get(f"/guides/xbox/{title.platform_title_id}")

        assert response.status_code == 200

    def test_game_guides_invalid_platform_aborts(
        self, client: FlaskClient
    ) -> None:
        """An unrecognised platform slug should abort with a redirect."""
        response = client.get("/guides/invalid/123")

        assert response.status_code == 302
