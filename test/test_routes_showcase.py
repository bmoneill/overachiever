"""Tests for :mod:`src.routes.showcase`.

Covers the four showcase endpoints:

* ``POST /showcase/add-game``
* ``POST /showcase/remove-game``
* ``POST /showcase/add-achievement``
* ``POST /showcase/remove-achievement``

Each test class exercises the happy path, validation failures, duplicate
detection, and the per-user cap enforced by the route constants
``MAX_PINNED_GAMES`` and ``MAX_PINNED_ACHIEVEMENTS``.
"""

from __future__ import annotations

from flask.testing import FlaskClient

from src.models.pinned_achievement import PinnedAchievement
from src.models.pinned_game import PinnedGame

# ------------------------------------------------------------------
# POST /showcase/add-game
# ------------------------------------------------------------------


class TestAddGame:
    """Tests for the ``POST /showcase/add-game`` route."""

    def test_add_game_success(
        self,
        auth_client: FlaskClient,
        auth_user,
        make_title,
        db_session,
    ) -> None:
        """Posting valid platform_id & title_id should pin the game and redirect."""
        title = make_title(name="Halo", platform=1, platform_title_id="200")
        db_session.commit()

        response = auth_client.post(
            "/showcase/add-game",
            data={
                "platform_id": str(title.platform),
                "title_id": title.platform_title_id,
                "redirect_url": "/",
            },
        )

        assert response.status_code == 302

        pinned = PinnedGame.query.filter_by(
            user_id=auth_user.id,
            title_id=title.id,
        ).first()
        assert pinned is not None

    def test_add_game_missing_info(
        self,
        auth_client: FlaskClient,
        db_session,
    ) -> None:
        """An empty platform_id should flash an error and redirect."""
        response = auth_client.post(
            "/showcase/add-game",
            data={
                "platform_id": "",
                "title_id": "999",
                "redirect_url": "/",
            },
        )

        assert response.status_code == 302

    def test_add_game_not_in_db(
        self,
        auth_client: FlaskClient,
        db_session,
    ) -> None:
        """Referencing a title that doesn't exist should flash an error."""
        response = auth_client.post(
            "/showcase/add-game",
            data={
                "platform_id": "1",
                "title_id": "nonexistent",
                "redirect_url": "/",
            },
        )

        assert response.status_code == 302
        assert PinnedGame.query.count() == 0

    def test_add_game_already_pinned(
        self,
        auth_client: FlaskClient,
        auth_user,
        make_title,
        db_session,
    ) -> None:
        """Pinning the same game twice should flash an error on the second attempt."""
        title = make_title(name="Halo", platform=1, platform_title_id="200")
        db_session.commit()

        # First pin – should succeed.
        auth_client.post(
            "/showcase/add-game",
            data={
                "platform_id": str(title.platform),
                "title_id": title.platform_title_id,
                "redirect_url": "/",
            },
        )

        assert (
            PinnedGame.query.filter_by(
                user_id=auth_user.id,
                title_id=title.id,
            ).count()
            == 1
        )

        # Second pin – should be rejected.
        response = auth_client.post(
            "/showcase/add-game",
            data={
                "platform_id": str(title.platform),
                "title_id": title.platform_title_id,
                "redirect_url": "/",
            },
        )

        assert response.status_code == 302
        assert (
            PinnedGame.query.filter_by(
                user_id=auth_user.id,
                title_id=title.id,
            ).count()
            == 1
        )

    def test_add_game_max_reached(
        self,
        auth_client: FlaskClient,
        auth_user,
        make_title,
        make_pinned_game,
        db_session,
    ) -> None:
        """After pinning 5 games the 6th attempt should be rejected."""
        for i in range(5):
            t = make_title(
                name=f"Game {i}",
                platform=1,
                platform_title_id=str(500 + i),
            )
            make_pinned_game(user=auth_user, title=t)
        db_session.commit()

        extra_title = make_title(
            name="Game Extra",
            platform=1,
            platform_title_id="999",
        )
        db_session.commit()

        response = auth_client.post(
            "/showcase/add-game",
            data={
                "platform_id": str(extra_title.platform),
                "title_id": extra_title.platform_title_id,
                "redirect_url": "/",
            },
        )

        assert response.status_code == 302
        assert PinnedGame.query.filter_by(user_id=auth_user.id).count() == 5

    def test_add_game_unauthenticated(
        self,
        client: FlaskClient,
        db_session,
    ) -> None:
        """An unauthenticated request should redirect to the login page."""
        response = client.post(
            "/showcase/add-game",
            data={
                "platform_id": "1",
                "title_id": "200",
                "redirect_url": "/",
            },
        )

        assert response.status_code == 302
        assert "/login" in response.headers.get("Location", "")


# ------------------------------------------------------------------
# POST /showcase/remove-game
# ------------------------------------------------------------------


class TestRemoveGame:
    """Tests for the ``POST /showcase/remove-game`` route."""

    def test_remove_game_success(
        self,
        auth_client: FlaskClient,
        auth_user,
        make_title,
        make_pinned_game,
        db_session,
    ) -> None:
        """Posting a valid pinned_game_id should delete the pin and redirect."""
        title = make_title(name="Halo", platform=1, platform_title_id="200")
        pg = make_pinned_game(user=auth_user, title=title)
        db_session.commit()

        pinned_game_id = pg.id

        response = auth_client.post(
            "/showcase/remove-game",
            data={
                "pinned_game_id": str(pinned_game_id),
                "redirect_url": "/",
            },
        )

        assert response.status_code == 302
        assert db_session.get(PinnedGame, pinned_game_id) is None

    def test_remove_game_missing_id(
        self,
        auth_client: FlaskClient,
        db_session,
    ) -> None:
        """An empty pinned_game_id should flash an error and redirect."""
        response = auth_client.post(
            "/showcase/remove-game",
            data={
                "pinned_game_id": "",
                "redirect_url": "/",
            },
        )

        assert response.status_code == 302


# ------------------------------------------------------------------
# POST /showcase/add-achievement
# ------------------------------------------------------------------


class TestAddAchievement:
    """Tests for the ``POST /showcase/add-achievement`` route."""

    def test_add_achievement_success(
        self,
        auth_client: FlaskClient,
        auth_user,
        make_title,
        make_achievement,
        db_session,
    ) -> None:
        """Posting valid fields should pin the achievement and redirect."""
        title = make_title(name="Halo", platform=1, platform_title_id="200")
        ach = make_achievement(title=title, achievement_name="First Blood")
        db_session.commit()

        response = auth_client.post(
            "/showcase/add-achievement",
            data={
                "platform_id": str(title.platform),
                "title_id": title.platform_title_id,
                "achievement_id": ach.achievement_id,
                "redirect_url": "/",
            },
        )

        assert response.status_code == 302

        pinned = PinnedAchievement.query.filter_by(
            user_id=auth_user.id,
            achievement_id=ach.id,
        ).first()
        assert pinned is not None

    def test_add_achievement_missing_info(
        self,
        auth_client: FlaskClient,
        db_session,
    ) -> None:
        """Empty required fields should flash an error and redirect."""
        response = auth_client.post(
            "/showcase/add-achievement",
            data={
                "platform_id": "",
                "title_id": "",
                "achievement_id": "",
                "redirect_url": "/",
            },
        )

        assert response.status_code == 302
        assert PinnedAchievement.query.count() == 0

    def test_add_achievement_not_in_db(
        self,
        auth_client: FlaskClient,
        db_session,
    ) -> None:
        """Referencing a nonexistent achievement should flash an error."""
        response = auth_client.post(
            "/showcase/add-achievement",
            data={
                "platform_id": "1",
                "title_id": "9999",
                "achievement_id": "no_such_ach",
                "redirect_url": "/",
            },
        )

        assert response.status_code == 302
        assert PinnedAchievement.query.count() == 0

    def test_add_achievement_already_pinned(
        self,
        auth_client: FlaskClient,
        auth_user,
        make_title,
        make_achievement,
        db_session,
    ) -> None:
        """Pinning the same achievement twice should flash an error on the second."""
        title = make_title(name="Halo", platform=1, platform_title_id="200")
        ach = make_achievement(title=title, achievement_name="First Blood")
        db_session.commit()

        form_data = {
            "platform_id": str(title.platform),
            "title_id": title.platform_title_id,
            "achievement_id": ach.achievement_id,
            "redirect_url": "/",
        }

        # First pin – should succeed.
        auth_client.post("/showcase/add-achievement", data=form_data)

        assert (
            PinnedAchievement.query.filter_by(
                user_id=auth_user.id,
                achievement_id=ach.id,
            ).count()
            == 1
        )

        # Second pin – should be rejected.
        response = auth_client.post(
            "/showcase/add-achievement",
            data=form_data,
        )

        assert response.status_code == 302
        assert (
            PinnedAchievement.query.filter_by(
                user_id=auth_user.id,
                achievement_id=ach.id,
            ).count()
            == 1
        )

    def test_add_achievement_max_reached(
        self,
        auth_client: FlaskClient,
        auth_user,
        make_title,
        make_achievement,
        make_pinned_achievement,
        db_session,
    ) -> None:
        """After pinning 5 achievements the 6th attempt should be rejected."""
        title = make_title(name="Halo", platform=1, platform_title_id="200")

        for i in range(5):
            ach = make_achievement(
                title=title,
                achievement_name=f"Ach {i}",
                achievement_id=str(3000 + i),
            )
            make_pinned_achievement(user=auth_user, achievement=ach)
        db_session.commit()

        extra_ach = make_achievement(
            title=title,
            achievement_name="Ach Extra",
            achievement_id="extra",
        )
        db_session.commit()

        response = auth_client.post(
            "/showcase/add-achievement",
            data={
                "platform_id": str(title.platform),
                "title_id": title.platform_title_id,
                "achievement_id": extra_ach.achievement_id,
                "redirect_url": "/",
            },
        )

        assert response.status_code == 302
        assert (
            PinnedAchievement.query.filter_by(user_id=auth_user.id).count() == 5
        )


# ------------------------------------------------------------------
# POST /showcase/remove-achievement
# ------------------------------------------------------------------


class TestRemoveAchievement:
    """Tests for the ``POST /showcase/remove-achievement`` route."""

    def test_remove_achievement_success(
        self,
        auth_client: FlaskClient,
        auth_user,
        make_title,
        make_achievement,
        make_pinned_achievement,
        db_session,
    ) -> None:
        """Posting a valid pinned_achievement_id should delete it and redirect."""
        title = make_title(name="Halo", platform=1, platform_title_id="200")
        ach = make_achievement(title=title, achievement_name="First Blood")
        pa = make_pinned_achievement(user=auth_user, achievement=ach)
        db_session.commit()

        pinned_achievement_id = pa.id

        response = auth_client.post(
            "/showcase/remove-achievement",
            data={
                "pinned_achievement_id": str(pinned_achievement_id),
                "redirect_url": "/",
            },
        )

        assert response.status_code == 302
        assert db_session.get(PinnedAchievement, pinned_achievement_id) is None
