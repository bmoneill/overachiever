"""Tests for the :func:`~src.routes.register.register` route.

Covers GET and POST behaviour for ``/register``, including
authentication guards, input validation, duplicate detection,
successful account creation, and the ``ALLOW_REGISTRATION`` toggle.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from flask.testing import FlaskClient

from src.models.user import User


class TestRegisterGet:
    """GET /register tests."""

    def test_register_get_returns_200(self, client: FlaskClient) -> None:
        """An unauthenticated GET should render the registration page."""
        response = client.get("/register")

        assert response.status_code == 200

    def test_register_get_authenticated_redirects(
        self, auth_client: FlaskClient
    ) -> None:
        """An authenticated GET should redirect to /my-games."""
        response = auth_client.get("/register")

        assert response.status_code == 302
        assert response.headers["Location"].endswith("/my-games")


class TestRegisterPostValidation:
    """POST /register tests for input validation."""

    def test_register_post_empty_fields_redirects(
        self, client: FlaskClient
    ) -> None:
        """POST with empty data should redirect back to /register."""
        response = client.post(
            "/register",
            data={"username": "", "email": "", "password": ""},
        )

        assert response.status_code == 302
        assert response.headers["Location"].endswith("/register")


class TestRegisterPostDuplicate:
    """POST /register tests for duplicate username / email detection."""

    def test_register_post_duplicate_username_redirects(
        self,
        client: FlaskClient,
        db_session,
        make_user,
    ) -> None:
        """POST with an existing username should redirect to /register."""
        make_user(
            username="taken",
            email="original@example.com",
            password_hash="hash",
        )
        db_session.commit()

        response = client.post(
            "/register",
            data={
                "username": "taken",
                "email": "new@example.com",
                "password": "secret123",
            },
        )

        assert response.status_code == 302
        assert response.headers["Location"].endswith("/register")

    def test_register_post_duplicate_email_redirects(
        self,
        client: FlaskClient,
        db_session,
        make_user,
    ) -> None:
        """POST with an existing email should redirect to /register."""
        make_user(
            username="origuser",
            email="taken@example.com",
            password_hash="hash",
        )
        db_session.commit()

        response = client.post(
            "/register",
            data={
                "username": "brandnew",
                "email": "taken@example.com",
                "password": "secret123",
            },
        )

        assert response.status_code == 302
        assert response.headers["Location"].endswith("/register")


class TestRegisterPostSuccess:
    """POST /register tests for successful account creation."""

    def test_register_post_success_creates_user(
        self,
        client: FlaskClient,
        db_session,
    ) -> None:
        """POST with valid, unique data should create a user and redirect to /login."""
        response = client.post(
            "/register",
            data={
                "username": "newuser",
                "email": "newuser@example.com",
                "password": "strongpass",
            },
        )

        assert response.status_code == 302
        assert response.headers["Location"].endswith("/login")

        created: User | None = User.query.filter_by(username="newuser").first()
        assert created is not None
        assert created.email == "newuser@example.com"
        # Password should be hashed, not stored in plain text.
        assert created.password_hash != "strongpass"


class TestRegisterDisabled:
    """Tests for the ``ALLOW_REGISTRATION`` toggle."""

    @patch("src.routes.register.ALLOW_REGISTRATION", False)
    def test_register_disabled_redirects_to_login(
        self, client: FlaskClient
    ) -> None:
        """When registration is disabled, GET should redirect to /login."""
        response = client.get("/register")

        assert response.status_code == 302
        assert response.headers["Location"].endswith("/login")
