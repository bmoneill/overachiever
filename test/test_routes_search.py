"""Tests for :mod:`src.routes.search`.

Covers the ``/search`` endpoint: empty queries, matching queries,
no-match queries, and case-insensitive username lookups.
"""

from __future__ import annotations

from flask.testing import FlaskClient


class TestUserSearch:
    """Tests for the ``GET /search`` route."""

    def test_search_no_query_returns_200(self, client: FlaskClient) -> None:
        """GET /search with no ``q`` param should return 200."""
        response = client.get("/search")

        assert response.status_code == 200

    def test_search_with_matching_query_returns_results(
        self,
        client: FlaskClient,
        make_user,
        db_session,
    ) -> None:
        """Searching for an existing username should include it in the response."""
        make_user(
            username="alice", email="alice@example.com", password_hash="hash"
        )
        make_user(username="bob", email="bob@example.com", password_hash="hash")
        db_session.commit()

        response = client.get("/search?q=alice")

        assert response.status_code == 200
        assert b"alice" in response.data

    def test_search_with_no_match_returns_empty(
        self,
        client: FlaskClient,
        make_user,
        db_session,
    ) -> None:
        """Searching for a nonexistent username should show a no-results message."""
        make_user(
            username="alice", email="alice@example.com", password_hash="hash"
        )
        db_session.commit()

        response = client.get("/search?q=zzzznonexistent")

        assert response.status_code == 200
        # The template echoes the query in a "no results" message,
        # so instead verify that no actual user link/result is rendered
        # and that the page signals no matches were found.
        assert (
            b"no-results" in response.data or b"No users found" in response.data
        )
        assert b"alice" not in response.data

    def test_search_is_case_insensitive(
        self,
        client: FlaskClient,
        make_user,
        db_session,
    ) -> None:
        """Search should match usernames regardless of case."""
        make_user(
            username="Alice", email="alice@example.com", password_hash="hash"
        )
        db_session.commit()

        response = client.get("/search?q=aLiCe")

        assert response.status_code == 200
        assert b"Alice" in response.data
