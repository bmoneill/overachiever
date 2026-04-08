"""Unit tests for the :class:`PinnedGame` model."""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError

from src.models.pinned_game import PinnedGame


class TestPinnedGameCreation:
    """Tests for basic PinnedGame creation and column defaults."""

    def test_create_pinned_game(
        self, db_session, make_pinned_game, make_user, make_title
    ):
        """A PinnedGame can be created with valid user and title."""
        user = make_user()
        title = make_title()
        pg = make_pinned_game(user=user, title=title)

        assert pg.id is not None
        assert pg.user_id == user.id
        assert pg.title_id == title.id

    def test_pinned_game_persisted(self, db_session, make_pinned_game):
        """PinnedGame is retrievable after flush."""
        pg = make_pinned_game()

        result = db_session.get(PinnedGame, pg.id)
        assert result is not None
        assert result.id == pg.id

    def test_multiple_pinned_games_for_same_user(
        self, db_session, make_pinned_game, make_user, make_title
    ):
        """A single user can pin multiple different games."""
        user = make_user()
        title_a = make_title(name="Game A")
        title_b = make_title(name="Game B")

        pg_a = make_pinned_game(user=user, title=title_a)
        pg_b = make_pinned_game(user=user, title=title_b)

        assert pg_a.id != pg_b.id
        assert pg_a.user_id == pg_b.user_id

    def test_same_title_pinned_by_different_users(
        self, db_session, make_pinned_game, make_user, make_title
    ):
        """Different users can pin the same game."""
        title = make_title()
        user_a = make_user()
        user_b = make_user()

        pg_a = make_pinned_game(user=user_a, title=title)
        pg_b = make_pinned_game(user=user_b, title=title)

        assert pg_a.id != pg_b.id
        assert pg_a.title_id == pg_b.title_id


class TestPinnedGameConstraints:
    """Tests for NOT NULL and foreign-key constraints."""

    def test_user_id_required(self, db_session, make_title):
        """Creating a PinnedGame without user_id raises IntegrityError."""
        title = make_title()
        pg = PinnedGame(title_id=title.id)
        db_session.add(pg)
        with pytest.raises(IntegrityError):
            db_session.flush()

    def test_title_id_required(self, db_session, make_user):
        """Creating a PinnedGame without title_id raises IntegrityError."""
        user = make_user()
        pg = PinnedGame(user_id=user.id)
        db_session.add(pg)
        with pytest.raises(IntegrityError):
            db_session.flush()


class TestPinnedGameRelationships:
    """Tests for the ``user`` and ``title`` relationships."""

    def test_user_relationship(
        self, db_session, make_pinned_game, make_user, make_title
    ):
        """The ``user`` relationship resolves to the correct User."""
        user = make_user(username="pinner")
        title = make_title()
        pg = make_pinned_game(user=user, title=title)

        assert pg.user is not None
        assert pg.user.id == user.id
        assert pg.user.username == "pinner"

    def test_title_relationship(
        self, db_session, make_pinned_game, make_user, make_title
    ):
        """The ``title`` relationship resolves to the correct Title."""
        user = make_user()
        title = make_title(name="Pinned Title")
        pg = make_pinned_game(user=user, title=title)

        assert pg.title is not None
        assert pg.title.id == title.id
        assert pg.title.name == "Pinned Title"

    def test_user_pinned_games_backref(
        self, db_session, make_pinned_game, make_user, make_title
    ):
        """The ``pinned_games`` backref on User contains the pinned game."""
        user = make_user()
        title = make_title()
        pg = make_pinned_game(user=user, title=title)

        pinned = user.pinned_games.all()
        assert len(pinned) == 1
        assert pinned[0].id == pg.id

    def test_title_pinned_by_backref(
        self, db_session, make_pinned_game, make_user, make_title
    ):
        """The ``pinned_by`` backref on Title contains the pinned game."""
        user = make_user()
        title = make_title()
        pg = make_pinned_game(user=user, title=title)

        pinned = title.pinned_by.all()
        assert len(pinned) == 1
        assert pinned[0].id == pg.id

    def test_multiple_users_in_title_pinned_by(
        self, db_session, make_pinned_game, make_user, make_title
    ):
        """The ``pinned_by`` backref collects pins from multiple users."""
        title = make_title()
        user_a = make_user()
        user_b = make_user()

        make_pinned_game(user=user_a, title=title)
        make_pinned_game(user=user_b, title=title)

        pinned = title.pinned_by.all()
        assert len(pinned) == 2
        user_ids = {p.user_id for p in pinned}
        assert user_ids == {user_a.id, user_b.id}


class TestPinnedGameTablename:
    """Verify the model's ``__tablename__``."""

    def test_tablename(self):
        """The table name should be ``pinned_games``."""
        assert PinnedGame.__tablename__ == "pinned_games"
