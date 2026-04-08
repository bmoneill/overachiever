"""Tests for :mod:`src.routes.index`.

Covers the index (``/``) route, verifying that unauthenticated visitors
receive a rendered landing page and authenticated users are redirected
to their timeline.
"""

from __future__ import annotations

from flask.testing import FlaskClient


class TestIndexRoute:
    """Tests for the ``GET /`` endpoint."""

    def test_index_unauthenticated_returns_200(
        self, client: FlaskClient
    ) -> None:
        """An unauthenticated GET / should return a 200 status code."""
        response = client.get("/")

        assert response.status_code == 200

    def test_index_authenticated_redirects_to_timeline(
        self, auth_client: FlaskClient
    ) -> None:
        """An authenticated GET / should redirect (302) to /timeline."""
        response = auth_client.get("/")

        assert response.status_code == 302
        assert "/timeline" in response.headers["Location"]
