"""Unit tests for the :func:`~src.routes._helpers` route helper utilities.

Covers:
- ``get_user_by_username`` – look-up by username
- ``load_user``            – Flask-Login user-loader callback
- ``get_platform_or_abort`` – platform slug → platform ID (or abort)
- ``get_user_or_abort``     – username → User (or abort)
- ``ALLOW_REGISTRATION``   – module-level constant default value
"""

from __future__ import annotations

import pytest
from werkzeug.exceptions import HTTPException

from src.routes._helpers import (
    ALLOW_REGISTRATION,
    get_platform_or_abort,
    get_user_by_username,
    get_user_or_abort,
    load_user,
)

# ------------------------------------------------------------------
# get_user_by_username
# ------------------------------------------------------------------


class TestGetUserByUsername:
    """Tests for :func:`get_user_by_username`."""

    def test_returns_user_when_found(self, db_session, make_user) -> None:
        """Should return the matching :class:`User` for an existing username."""
        user = make_user(
            username="alice",
            email="alice@example.com",
            password_hash="hash",
        )
        db_session.commit()

        result = get_user_by_username("alice")

        assert result is not None
        assert result.id == user.id
        assert result.username == "alice"

    def test_returns_none_when_not_found(self, db_session) -> None:
        """Should return ``None`` when no user matches the username."""
        result = get_user_by_username("nonexistent")

        assert result is None


# ------------------------------------------------------------------
# load_user
# ------------------------------------------------------------------


class TestLoadUser:
    """Tests for the Flask-Login :func:`load_user` callback."""

    def test_returns_user_for_valid_id(self, db_session, make_user) -> None:
        """Should return the :class:`User` whose PK matches *user_id*."""
        user = make_user(
            username="bob",
            email="bob@example.com",
            password_hash="hash",
        )
        db_session.commit()

        result = load_user(user.id)

        assert result is not None
        assert result.id == user.id
        assert result.username == "bob"

    def test_returns_none_for_nonexistent_id(self, db_session) -> None:
        """Should return ``None`` when no user has the given PK."""
        result = load_user(99999)

        assert result is None


# ------------------------------------------------------------------
# get_platform_or_abort
# ------------------------------------------------------------------


class TestGetPlatformOrAbort:
    """Tests for :func:`get_platform_or_abort`."""

    @pytest.mark.parametrize(
        ("slug", "expected_id"),
        [
            ("psn", 0),
            ("xbox", 1),
            ("steam", 2),
        ],
    )
    def test_returns_platform_id_for_valid_slug(
        self,
        route_app,
        db_session,
        slug: str,
        expected_id: int,
    ) -> None:
        """Should return the integer platform ID for a known slug."""
        with route_app.test_request_context():
            result = get_platform_or_abort(slug)

        assert result == expected_id

    def test_aborts_with_redirect_for_invalid_slug(
        self,
        route_app,
        db_session,
    ) -> None:
        """Should abort with a redirect when the platform slug is unknown."""
        with route_app.test_request_context():
            with pytest.raises(HTTPException) as exc_info:
                get_platform_or_abort("nintendo")

        response = exc_info.value.response
        assert response is not None
        assert response.status_code == 302

    def test_abort_redirect_uses_custom_endpoint(
        self,
        route_app,
        db_session,
    ) -> None:
        """Should redirect to the endpoint specified by *redirect_to*."""
        with route_app.test_request_context():
            with pytest.raises(HTTPException) as exc_info:
                get_platform_or_abort("bad", redirect_to="login")

        response = exc_info.value.response
        assert response is not None
        assert "/login" in response.headers.get("Location", "")


# ------------------------------------------------------------------
# get_user_or_abort
# ------------------------------------------------------------------


class TestGetUserOrAbort:
    """Tests for :func:`get_user_or_abort`."""

    def test_returns_user_for_valid_username(
        self,
        route_app,
        db_session,
        make_user,
    ) -> None:
        """Should return the :class:`User` when the username exists."""
        user = make_user(
            username="carol",
            email="carol@example.com",
            password_hash="hash",
        )
        db_session.commit()

        with route_app.test_request_context():
            result = get_user_or_abort("carol")

        assert result is not None
        assert result.id == user.id
        assert result.username == "carol"

    def test_aborts_with_redirect_for_missing_username(
        self,
        route_app,
        db_session,
    ) -> None:
        """Should abort with a redirect when the username does not exist."""
        with route_app.test_request_context():
            with pytest.raises(HTTPException) as exc_info:
                get_user_or_abort("ghost")

        response = exc_info.value.response
        assert response is not None
        assert response.status_code == 302

    def test_abort_redirect_uses_custom_endpoint(
        self,
        route_app,
        db_session,
    ) -> None:
        """Should redirect to the endpoint specified by *redirect_to*."""
        with route_app.test_request_context():
            with pytest.raises(HTTPException) as exc_info:
                get_user_or_abort("nobody", redirect_to="login")

        response = exc_info.value.response
        assert response is not None
        assert "/login" in response.headers.get("Location", "")


# ------------------------------------------------------------------
# ALLOW_REGISTRATION
# ------------------------------------------------------------------


class TestAllowRegistration:
    """Tests for the :data:`ALLOW_REGISTRATION` module-level constant."""

    def test_default_is_true(self) -> None:
        """``ALLOW_REGISTRATION`` should be ``True`` when the env var is unset or 'true'."""
        assert ALLOW_REGISTRATION is True
