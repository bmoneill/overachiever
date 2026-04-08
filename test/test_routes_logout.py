"""Tests for :mod:`src.routes.logout`.

Verifies that the ``/logout`` endpoint correctly logs out an
authenticated user and redirects to the login page, and that
unauthenticated requests are bounced by ``login_required``.
"""

from __future__ import annotations

from flask.testing import FlaskClient


class TestLogoutRoute:
    """Tests for the ``GET /logout`` endpoint."""

    def test_logout_authenticated_redirects_to_login(
        self, auth_client: FlaskClient
    ) -> None:
        """An authenticated user hitting /logout should be logged out and
        redirected (302) to the /login page."""
        response = auth_client.get("/logout")

        assert response.status_code == 302
        assert response.headers["Location"].endswith("/login")

    def test_logout_unauthenticated_redirects_to_login(
        self, client: FlaskClient
    ) -> None:
        """An unauthenticated request to /logout should be redirected to
        /login by the ``login_required`` decorator."""
        response = client.get("/logout")

        assert response.status_code == 302
        assert "/login" in response.headers["Location"]
