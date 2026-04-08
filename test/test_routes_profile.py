"""Tests for :mod:`src.routes.profile`.

Covers the profile page (``/profile/<username>``), profile editing,
following, and unfollowing endpoints.  External API calls
(:class:`XboxProfileAPI`, :class:`SteamProfileAPI`, and
:func:`resolve_xbox_icon_fallbacks`) are mocked so that no real
network I/O occurs during tests.
"""

from __future__ import annotations

from unittest.mock import patch

from flask.testing import FlaskClient

from src.models.user import User
from src.models.user_follow import UserFollow

# ------------------------------------------------------------------
# GET /profile/<username>
# ------------------------------------------------------------------


class TestProfilePage:
    """Tests for the ``GET /profile/<username>`` endpoint."""

    @patch("src.routes.profile.resolve_xbox_icon_fallbacks")
    @patch("src.routes.profile.SteamProfileAPI")
    @patch("src.routes.profile.XboxProfileAPI")
    def test_profile_existing_user_returns_200(
        self,
        mock_xbox_api: object,
        mock_steam_api: object,
        mock_resolve: object,
        client: FlaskClient,
        make_user,
        db_session,
    ) -> None:
        """GET /profile/<username> for an existing user returns 200."""
        make_user(username="alice", email="alice@example.com")
        db_session.commit()

        response = client.get("/profile/alice")

        assert response.status_code == 200

    def test_profile_nonexistent_user_aborts(
        self,
        client: FlaskClient,
    ) -> None:
        """GET /profile/nobody should redirect (abort via redirect)."""
        response = client.get("/profile/nobody")

        assert response.status_code == 302


# ------------------------------------------------------------------
# POST /profile/<username>/edit
# ------------------------------------------------------------------


class TestProfileEdit:
    """Tests for the ``GET|POST /profile/<username>/edit`` endpoint."""

    def test_profile_edit_own_profile_get_returns_200(
        self,
        auth_client: FlaskClient,
    ) -> None:
        """GET /profile/testuser/edit as the authenticated user returns 200."""
        response = auth_client.get("/profile/testuser/edit")

        assert response.status_code == 200

    def test_profile_edit_other_profile_redirects(
        self,
        auth_client: FlaskClient,
        make_user,
        db_session,
    ) -> None:
        """POST /profile/otheruser/edit as auth user redirects with 302."""
        make_user(username="otheruser", email="other@example.com")
        db_session.commit()

        response = auth_client.post(
            "/profile/otheruser/edit",
            data={"bio": "hacked"},
        )

        assert response.status_code == 302
        assert "/profile/otheruser" in response.headers["Location"]

    @patch("src.routes.profile.resolve_xbox_icon_fallbacks")
    def test_profile_edit_updates_bio(
        self,
        mock_resolve: object,
        auth_client: FlaskClient,
        db_session,
    ) -> None:
        """POST /profile/testuser/edit with bio updates the user's bio."""
        response = auth_client.post(
            "/profile/testuser/edit",
            data={"bio": "hello"},
        )

        assert response.status_code == 302
        assert "/profile/testuser" in response.headers["Location"]

        user = User.query.filter_by(username="testuser").first()
        assert user is not None
        assert user.bio == "hello"

    def test_profile_edit_unauthenticated_redirects(
        self,
        client: FlaskClient,
    ) -> None:
        """POST /profile/testuser/edit when not logged in redirects to login."""
        response = client.post(
            "/profile/testuser/edit",
            data={"bio": "sneaky"},
        )

        assert response.status_code == 302
        assert "/login" in response.headers["Location"]


# ------------------------------------------------------------------
# POST /profile/<username>/follow
# ------------------------------------------------------------------


class TestFollowUser:
    """Tests for the ``POST /profile/<username>/follow`` endpoint."""

    @patch("src.routes.profile.resolve_xbox_icon_fallbacks")
    def test_follow_user_success(
        self,
        mock_resolve: object,
        auth_client: FlaskClient,
        make_user,
        db_session,
    ) -> None:
        """Following another user creates a UserFollow row and redirects."""
        target = make_user(username="target", email="target@example.com")
        db_session.commit()

        response = auth_client.post("/profile/target/follow")

        assert response.status_code == 302
        assert "/profile/target" in response.headers["Location"]

        follow = UserFollow.query.filter_by(
            follower_id=auth_client._user.id,  # type: ignore[attr-defined]
            followed_id=target.id,
        ).first()
        assert follow is not None

    def test_follow_self_fails(
        self,
        auth_client: FlaskClient,
    ) -> None:
        """Attempting to follow yourself flashes an error and redirects."""
        response = auth_client.post("/profile/testuser/follow")

        assert response.status_code == 302
        assert "/profile/testuser" in response.headers["Location"]

        follow = UserFollow.query.filter_by(
            follower_id=auth_client._user.id,  # type: ignore[attr-defined]
            followed_id=auth_client._user.id,  # type: ignore[attr-defined]
        ).first()
        assert follow is None

    @patch("src.routes.profile.resolve_xbox_icon_fallbacks")
    def test_follow_already_following_no_duplicate(
        self,
        mock_resolve: object,
        auth_client: FlaskClient,
        make_user,
        make_user_follow,
        db_session,
    ) -> None:
        """Following a user you already follow should not create a duplicate."""
        target = make_user(username="target", email="target@example.com")
        auth_user: User = auth_client._user  # type: ignore[attr-defined]
        make_user_follow(follower=auth_user, followed=target)
        db_session.commit()

        response = auth_client.post("/profile/target/follow")

        assert response.status_code == 302

        count = UserFollow.query.filter_by(
            follower_id=auth_user.id,
            followed_id=target.id,
        ).count()
        assert count == 1

    def test_follow_unauthenticated_redirects(
        self,
        client: FlaskClient,
        make_user,
        db_session,
    ) -> None:
        """POST /profile/<user>/follow when not logged in redirects to login."""
        make_user(username="target", email="target@example.com")
        db_session.commit()

        response = client.post("/profile/target/follow")

        assert response.status_code == 302
        assert "/login" in response.headers["Location"]


# ------------------------------------------------------------------
# POST /profile/<username>/unfollow
# ------------------------------------------------------------------


class TestUnfollowUser:
    """Tests for the ``POST /profile/<username>/unfollow`` endpoint."""

    @patch("src.routes.profile.resolve_xbox_icon_fallbacks")
    def test_unfollow_user_success(
        self,
        mock_resolve: object,
        auth_client: FlaskClient,
        make_user,
        make_user_follow,
        db_session,
    ) -> None:
        """Unfollowing a followed user deletes the UserFollow row."""
        target = make_user(username="target", email="target@example.com")
        auth_user: User = auth_client._user  # type: ignore[attr-defined]
        make_user_follow(follower=auth_user, followed=target)
        db_session.commit()

        response = auth_client.post("/profile/target/unfollow")

        assert response.status_code == 302
        assert "/profile/target" in response.headers["Location"]

        follow = UserFollow.query.filter_by(
            follower_id=auth_user.id,
            followed_id=target.id,
        ).first()
        assert follow is None

    @patch("src.routes.profile.resolve_xbox_icon_fallbacks")
    def test_unfollow_not_following_no_error(
        self,
        mock_resolve: object,
        auth_client: FlaskClient,
        make_user,
        db_session,
    ) -> None:
        """Unfollowing someone you don't follow just redirects without error."""
        make_user(username="stranger", email="stranger@example.com")
        db_session.commit()

        response = auth_client.post("/profile/stranger/unfollow")

        assert response.status_code == 302
        assert "/profile/stranger" in response.headers["Location"]
