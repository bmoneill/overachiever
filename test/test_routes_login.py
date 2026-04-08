"""Tests for :mod:`src.routes.login`.

Covers the ``/login`` route: rendering the login page, redirecting
authenticated users, and handling valid / invalid POST submissions.
"""

from __future__ import annotations

import pytest
from flask import Flask
from werkzeug.security import generate_password_hash

# ===================================================================
# GET /login
# ===================================================================


class TestLoginGet:
    """Tests for ``GET /login``."""

    def test_login_get_returns_200(self, client) -> None:
        """An unauthenticated GET to ``/login`` should return 200."""
        response = client.get("/login")

        assert response.status_code == 200

    def test_login_get_authenticated_redirects(self, auth_client) -> None:
        """An already-authenticated GET to ``/login`` should redirect to ``/my-games``."""
        response = auth_client.get("/login")

        assert response.status_code == 302
        assert response.headers["Location"].endswith("/my-games")


# ===================================================================
# POST /login — validation failures
# ===================================================================


class TestLoginPostValidation:
    """Tests for ``POST /login`` when input is missing or wrong."""

    def test_login_post_empty_fields_redirects(self, client) -> None:
        """POST with empty username and password should redirect back to ``/login``."""
        response = client.post("/login", data={"username": "", "password": ""})

        assert response.status_code == 302
        assert response.headers["Location"].endswith("/login")

    def test_login_post_invalid_credentials_redirects(
        self, client, db_session, make_user
    ) -> None:
        """POST with a wrong password should redirect back to ``/login``."""
        make_user(
            username="alice",
            email="alice@example.com",
            password_hash=generate_password_hash("correctpassword"),
        )
        db_session.commit()

        response = client.post(
            "/login",
            data={"username": "alice", "password": "wrongpassword"},
        )

        assert response.status_code == 302
        assert response.headers["Location"].endswith("/login")


# ===================================================================
# POST /login — successful authentication
# ===================================================================


class TestLoginPostSuccess:
    """Tests for ``POST /login`` with valid credentials."""

    def test_login_post_valid_credentials_redirects_to_my_games(
        self, client, db_session, make_user
    ) -> None:
        """POST with correct credentials should redirect to ``/my-games``."""
        make_user(
            username="alice",
            email="alice@example.com",
            password_hash=generate_password_hash("mypass"),
        )
        db_session.commit()

        response = client.post(
            "/login",
            data={"username": "alice", "password": "mypass"},
        )

        assert response.status_code == 302
        assert response.headers["Location"].endswith("/my-games")

    def test_login_post_with_next_param(
        self, client, db_session, make_user
    ) -> None:
        """POST with a ``?next`` query parameter should redirect to that URL."""
        make_user(
            username="alice",
            email="alice@example.com",
            password_hash=generate_password_hash("mypass"),
        )
        db_session.commit()

        response = client.post(
            "/login?next=/settings",
            data={"username": "alice", "password": "mypass"},
        )

        assert response.status_code == 302
        assert response.headers["Location"].endswith("/settings")
