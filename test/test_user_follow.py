"""Unit tests for the :class:`UserFollow` model."""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError

from src.models.user_follow import UserFollow


class TestUserFollowCreation:
    """Tests for basic ``UserFollow`` creation and column defaults."""

    def test_create_user_follow(self, make_user_follow):
        """A follow relationship can be created between two users."""
        uf = make_user_follow()

        assert uf.id is not None
        assert uf.follower_id is not None
        assert uf.followed_id is not None
        assert uf.follower_id != uf.followed_id

    def test_created_at_has_default(self, make_user_follow):
        """The ``created_at`` column should receive a default ISO timestamp."""
        uf = make_user_follow()

        assert uf.created_at is not None
        # ISO-8601 timestamps always contain a "T" separator
        assert "T" in uf.created_at

    def test_explicit_created_at(self, make_user, make_user_follow):
        """An explicit ``created_at`` value should be preserved."""
        follower = make_user()
        followed = make_user()
        uf = make_user_follow(
            follower=follower,
            followed=followed,
            created_at="2024-01-15T12:00:00+00:00",
        )

        assert uf.created_at == "2024-01-15T12:00:00+00:00"


class TestUserFollowConstraints:
    """Tests for unique constraints and foreign-key requirements."""

    def test_follower_id_not_nullable(self, db_session, make_user):
        """``follower_id`` must not be null."""
        followed = make_user()
        uf = UserFollow(follower_id=None, followed_id=followed.id)
        db_session.add(uf)

        with pytest.raises(IntegrityError):
            db_session.flush()

    def test_followed_id_not_nullable(self, db_session, make_user):
        """``followed_id`` must not be null."""
        follower = make_user()
        uf = UserFollow(follower_id=follower.id, followed_id=None)
        db_session.add(uf)

        with pytest.raises(IntegrityError):
            db_session.flush()

    def test_duplicate_follow_raises(
        self, db_session, make_user, make_user_follow
    ):
        """The unique constraint ``(follower_id, followed_id)`` must be enforced."""
        follower = make_user()
        followed = make_user()
        make_user_follow(follower=follower, followed=followed)

        duplicate = UserFollow(follower_id=follower.id, followed_id=followed.id)
        db_session.add(duplicate)

        with pytest.raises(IntegrityError):
            db_session.flush()

    def test_reverse_follow_allowed(self, make_user, make_user_follow):
        """User A following B and B following A should both be allowed."""
        user_a = make_user()
        user_b = make_user()

        uf1 = make_user_follow(follower=user_a, followed=user_b)
        uf2 = make_user_follow(follower=user_b, followed=user_a)

        assert uf1.id != uf2.id
        assert uf1.follower_id == uf2.followed_id
        assert uf1.followed_id == uf2.follower_id


class TestUserFollowRelationships:
    """Tests for the ``follower`` and ``followed`` relationships."""

    def test_follower_relationship(self, make_user, make_user_follow):
        """The ``follower`` relationship should resolve to the correct user."""
        user = make_user(username="alpha")
        uf = make_user_follow(follower=user)

        assert uf.follower is user
        assert uf.follower.username == "alpha"

    def test_followed_relationship(self, make_user, make_user_follow):
        """The ``followed`` relationship should resolve to the correct user."""
        user = make_user(username="beta")
        uf = make_user_follow(followed=user)

        assert uf.followed is user
        assert uf.followed.username == "beta"

    def test_user_following_backref(self, make_user, make_user_follow):
        """A user's ``following`` backref should list users they follow."""
        user_a = make_user()
        user_b = make_user()
        user_c = make_user()

        make_user_follow(follower=user_a, followed=user_b)
        make_user_follow(follower=user_a, followed=user_c)

        following_ids = {uf.followed_id for uf in user_a.following}
        assert following_ids == {user_b.id, user_c.id}

    def test_user_followers_backref(self, make_user, make_user_follow):
        """A user's ``followers`` backref should list their followers."""
        user_a = make_user()
        user_b = make_user()
        user_c = make_user()

        make_user_follow(follower=user_b, followed=user_a)
        make_user_follow(follower=user_c, followed=user_a)

        follower_ids = {uf.follower_id for uf in user_a.followers}
        assert follower_ids == {user_b.id, user_c.id}

    def test_following_and_followers_independent(
        self, make_user, make_user_follow
    ):
        """``following`` and ``followers`` should be independent collections."""
        user_a = make_user()
        user_b = make_user()

        make_user_follow(follower=user_a, followed=user_b)

        assert user_a.following.count() == 1
        assert user_a.followers.count() == 0
        assert user_b.following.count() == 0
        assert user_b.followers.count() == 1


class TestUserFollowTableArgs:
    """Tests for table-level metadata."""

    def test_tablename(self):
        """The table name should be ``user_follows``."""
        assert UserFollow.__tablename__ == "user_follows"
