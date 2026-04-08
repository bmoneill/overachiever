"""Tests for :mod:`src.routes.settings`.

Covers the settings page (``GET /settings``), Xbox linking / unlinking
(``POST /settings/xbox/link``, ``POST /settings/xbox/unlink``), and
Steam linking / unlinking (``POST /settings/steam/link``,
``POST /settings/steam/unlink``).
"""

from __future__ import annotations

from flask.testing import FlaskClient

from src.models.user import User


class TestSettingsPage:
    """Tests for the ``GET /settings`` endpoint."""

    def test_settings_unauthenticated_redirects(
        self, client: FlaskClient
    ) -> None:
        """An unauthenticated GET /settings should redirect (302) to /login."""
        response = client.get("/settings")

        assert response.status_code == 302
        assert "/login" in response.headers["Location"]

    def test_settings_authenticated_returns_200(
        self, auth_client: FlaskClient
    ) -> None:
        """An authenticated GET /settings should return 200."""
        response = auth_client.get("/settings")

        assert response.status_code == 200


class TestXboxLink:
    """Tests for the ``POST /settings/xbox/link`` endpoint."""

    def test_xbox_link_empty_xuid(self, auth_client: FlaskClient) -> None:
        """Submitting an empty XUID should redirect back to /settings."""
        response = auth_client.post(
            "/settings/xbox/link",
            data={"xuid": ""},
        )

        assert response.status_code == 302
        assert "/settings" in response.headers["Location"]

    def test_xbox_link_non_numeric_xuid(self, auth_client: FlaskClient) -> None:
        """Submitting a non-numeric XUID (e.g. 'abc') should redirect back."""
        response = auth_client.post(
            "/settings/xbox/link",
            data={"xuid": "abc"},
        )

        assert response.status_code == 302
        assert "/settings" in response.headers["Location"]

    def test_xbox_link_already_linked(
        self, auth_client: FlaskClient, auth_user: User, db_session
    ) -> None:
        """If the user already has an XUID, linking should be rejected."""
        auth_user.xuid = "1111111111"
        db_session.commit()

        response = auth_client.post(
            "/settings/xbox/link",
            data={"xuid": "2222222222"},
        )

        assert response.status_code == 302
        assert "/settings" in response.headers["Location"]

        db_session.refresh(auth_user)
        assert auth_user.xuid == "1111111111"

    def test_xbox_link_taken_by_other_user(
        self,
        auth_client: FlaskClient,
        auth_user: User,
        make_user,
        db_session,
    ) -> None:
        """Linking an XUID that belongs to another user should be rejected."""
        other = make_user(
            username="otheruser",
            email="other@example.com",
            password_hash="hash",
            xuid="9999999999",
        )
        db_session.commit()

        response = auth_client.post(
            "/settings/xbox/link",
            data={"xuid": "9999999999"},
        )

        assert response.status_code == 302
        assert "/settings" in response.headers["Location"]

        db_session.refresh(auth_user)
        assert auth_user.xuid is None

    def test_xbox_link_success(
        self, auth_client: FlaskClient, auth_user: User, db_session
    ) -> None:
        """A valid, unclaimed XUID should be linked to the user."""
        response = auth_client.post(
            "/settings/xbox/link",
            data={"xuid": "1234567890"},
        )

        assert response.status_code == 302
        assert "/settings" in response.headers["Location"]

        db_session.refresh(auth_user)
        assert auth_user.xuid == "1234567890"


class TestXboxUnlink:
    """Tests for the ``POST /settings/xbox/unlink`` endpoint."""

    def test_xbox_unlink_success(
        self, auth_client: FlaskClient, auth_user: User, db_session
    ) -> None:
        """Unlinking should clear the user's XUID and redirect."""
        auth_user.xuid = "1234567890"
        db_session.commit()

        response = auth_client.post("/settings/xbox/unlink")

        assert response.status_code == 302
        assert "/settings" in response.headers["Location"]

        db_session.refresh(auth_user)
        assert auth_user.xuid is None


class TestSteamLink:
    """Tests for the ``POST /settings/steam/link`` endpoint."""

    def test_steam_link_empty_input(self, auth_client: FlaskClient) -> None:
        """Submitting an empty Steam input should redirect back."""
        response = auth_client.post(
            "/settings/steam/link",
            data={"steam_input_type": "steam_id", "steam_input": ""},
        )

        assert response.status_code == 302
        assert "/settings" in response.headers["Location"]

    def test_steam_link_non_numeric_steam_id(
        self, auth_client: FlaskClient
    ) -> None:
        """A non-numeric value with input_type 'steam_id' should be rejected."""
        response = auth_client.post(
            "/settings/steam/link",
            data={"steam_input_type": "steam_id", "steam_input": "abc"},
        )

        assert response.status_code == 302
        assert "/settings" in response.headers["Location"]

    def test_steam_link_already_linked(
        self, auth_client: FlaskClient, auth_user: User, db_session
    ) -> None:
        """If the user already has a Steam ID, linking should be rejected."""
        auth_user.steam_id = "11111111111111111"
        db_session.commit()

        response = auth_client.post(
            "/settings/steam/link",
            data={
                "steam_input_type": "steam_id",
                "steam_input": "22222222222222222",
            },
        )

        assert response.status_code == 302
        assert "/settings" in response.headers["Location"]

        db_session.refresh(auth_user)
        assert auth_user.steam_id == "11111111111111111"

    def test_steam_link_taken_by_other_user(
        self,
        auth_client: FlaskClient,
        auth_user: User,
        make_user,
        db_session,
    ) -> None:
        """Linking a Steam ID that belongs to another user should be rejected."""
        other = make_user(
            username="othersteam",
            email="othersteam@example.com",
            password_hash="hash",
            steam_id="99999999999999999",
        )
        db_session.commit()

        response = auth_client.post(
            "/settings/steam/link",
            data={
                "steam_input_type": "steam_id",
                "steam_input": "99999999999999999",
            },
        )

        assert response.status_code == 302
        assert "/settings" in response.headers["Location"]

        db_session.refresh(auth_user)
        assert auth_user.steam_id is None

    def test_steam_link_success(
        self, auth_client: FlaskClient, auth_user: User, db_session
    ) -> None:
        """A valid, unclaimed Steam ID should be linked to the user."""
        response = auth_client.post(
            "/settings/steam/link",
            data={
                "steam_input_type": "steam_id",
                "steam_input": "76561198000000001",
            },
        )

        assert response.status_code == 302
        assert "/settings" in response.headers["Location"]

        db_session.refresh(auth_user)
        assert auth_user.steam_id == "76561198000000001"


class TestSteamUnlink:
    """Tests for the ``POST /settings/steam/unlink`` endpoint."""

    def test_steam_unlink_success(
        self, auth_client: FlaskClient, auth_user: User, db_session
    ) -> None:
        """Unlinking should clear the user's Steam ID and redirect."""
        auth_user.steam_id = "76561198000000001"
        db_session.commit()

        response = auth_client.post("/settings/steam/unlink")

        assert response.status_code == 302
        assert "/settings" in response.headers["Location"]

        db_session.refresh(auth_user)
        assert auth_user.steam_id is None
