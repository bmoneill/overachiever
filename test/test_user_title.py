"""Unit tests for :class:`~src.models.user_title.UserTitle`."""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError

from src.models.user_title import UserTitle


class TestUserTitleCreation:
    """Tests for basic UserTitle instantiation and column defaults."""

    def test_create_user_title_defaults(
        self, db_session, make_user_title
    ) -> None:
        """A UserTitle created without optional fields gets correct defaults."""
        ut = make_user_title()

        assert ut.id is not None
        assert ut.user_id is not None
        assert ut.title_id is not None
        assert ut.current_achievements is None
        assert ut.progress_percentage is None
        assert ut.last_played is None

    def test_create_user_title_with_all_fields(
        self, db_session, make_user, make_title
    ) -> None:
        """A UserTitle can be created with explicit values for every column."""
        user = make_user()
        title = make_title(total_achievements=50)
        ut = UserTitle(
            user_id=user.id,
            title_id=title.id,
            current_achievements=25,
            progress_percentage=50,
            last_played="2024-06-15T12:00:00Z",
        )
        db_session.add(ut)
        db_session.flush()

        assert ut.current_achievements == 25
        assert ut.progress_percentage == 50
        assert ut.last_played == "2024-06-15T12:00:00Z"

    def test_persisted_to_database(self, db_session, make_user_title) -> None:
        """A flushed UserTitle can be queried back from the database."""
        ut = make_user_title()
        result = db_session.get(UserTitle, ut.id)
        assert result is not None
        assert result.id == ut.id


class TestUserTitleRelationships:
    """Tests for user and title relationships / back-references."""

    def test_user_relationship(self, db_session, make_user, make_title) -> None:
        """The ``user`` relationship resolves to the correct User."""
        user = make_user(username="gamer1")
        title = make_title()
        ut = make_user_title_instance(db_session, user, title)

        assert ut.user is not None
        assert ut.user.username == "gamer1"

    def test_title_relationship(
        self, db_session, make_user, make_title
    ) -> None:
        """The ``title`` relationship resolves to the correct Title."""
        user = make_user()
        title = make_title(name="Halo Infinite")
        ut = make_user_title_instance(db_session, user, title)

        assert ut.title is not None
        assert ut.title.name == "Halo Infinite"

    def test_user_backref_user_titles(
        self, db_session, make_user, make_title
    ) -> None:
        """Creating UserTitle entries populates ``user.user_titles``."""
        user = make_user()
        t1 = make_title(name="Game A", platform_title_id="901")
        t2 = make_title(name="Game B", platform_title_id="902")
        make_user_title_instance(db_session, user, t1)
        make_user_title_instance(db_session, user, t2)

        assert user.user_titles.count() == 2

    def test_title_backref_user_titles(
        self, db_session, make_user, make_title
    ) -> None:
        """Creating UserTitle entries populates ``title.user_titles``."""
        title = make_title()
        u1 = make_user(username="player1", email="p1@test.com")
        u2 = make_user(username="player2", email="p2@test.com")
        make_user_title_instance(db_session, u1, title)
        make_user_title_instance(db_session, u2, title)

        assert title.user_titles.count() == 2


class TestUserTitleUniqueConstraint:
    """Tests for the ``uq_user_title`` unique constraint."""

    def test_duplicate_user_title_raises(
        self, db_session, make_user, make_title
    ) -> None:
        """Inserting the same (user_id, title_id) pair twice must fail."""
        user = make_user()
        title = make_title()
        make_user_title_instance(db_session, user, title)

        duplicate = UserTitle(user_id=user.id, title_id=title.id)
        db_session.add(duplicate)
        with pytest.raises(IntegrityError):
            db_session.flush()
        db_session.rollback()

    def test_same_user_different_titles_ok(
        self, db_session, make_user, make_title
    ) -> None:
        """The same user may have entries for different titles."""
        user = make_user()
        t1 = make_title(platform_title_id="801")
        t2 = make_title(platform_title_id="802")
        make_user_title_instance(db_session, user, t1)
        make_user_title_instance(db_session, user, t2)
        db_session.flush()

        assert user.user_titles.count() == 2

    def test_same_title_different_users_ok(
        self, db_session, make_user, make_title
    ) -> None:
        """Different users may each have an entry for the same title."""
        title = make_title()
        u1 = make_user(username="a", email="a@test.com")
        u2 = make_user(username="b", email="b@test.com")
        make_user_title_instance(db_session, u1, title)
        make_user_title_instance(db_session, u2, title)
        db_session.flush()

        assert title.user_titles.count() == 2


class TestUserTitleConvenienceProperties:
    """Tests for proxy / convenience properties that delegate to Title."""

    def test_total_achievements(
        self, db_session, make_user, make_title
    ) -> None:
        """``total_achievements`` proxies ``title.total_achievements``."""
        title = make_title(total_achievements=42)
        ut = make_user_title_instance(db_session, make_user(), title)

        assert ut.total_achievements == 42

    def test_platform_xbox(self, db_session, make_user, make_title) -> None:
        """``platform`` returns ``'xbox'`` for platform id 1."""
        title = make_title(platform=1)
        ut = make_user_title_instance(db_session, make_user(), title)

        assert ut.platform == "xbox"

    def test_platform_steam(self, db_session, make_user, make_title) -> None:
        """``platform`` returns ``'steam'`` for platform id 2."""
        title = make_title(platform=2)
        ut = make_user_title_instance(db_session, make_user(), title)

        assert ut.platform == "steam"

    def test_platform_psn(self, db_session, make_user, make_title) -> None:
        """``platform`` returns ``'psn'`` for platform id 0."""
        title = make_title(platform=0)
        ut = make_user_title_instance(db_session, make_user(), title)

        assert ut.platform == "psn"

    def test_platform_unknown(self, db_session, make_user, make_title) -> None:
        """``platform`` returns ``'unknown'`` for unrecognised platform ids."""
        title = make_title(platform=999)
        ut = make_user_title_instance(db_session, make_user(), title)

        assert ut.platform == "unknown"

    def test_platform_title_id(self, db_session, make_user, make_title) -> None:
        """``platform_title_id`` proxies ``title.platform_title_id``."""
        title = make_title(platform_title_id="ABC123")
        ut = make_user_title_instance(db_session, make_user(), title)

        assert ut.platform_title_id == "ABC123"

    def test_name(self, db_session, make_user, make_title) -> None:
        """``name`` proxies ``title.name``."""
        title = make_title(name="Elden Ring")
        ut = make_user_title_instance(db_session, make_user(), title)

        assert ut.name == "Elden Ring"

    def test_image_url(self, db_session, make_user, make_title) -> None:
        """``image_url`` proxies ``title.image_url``."""
        title = make_title(image_url="https://example.com/cover.jpg")
        ut = make_user_title_instance(db_session, make_user(), title)

        assert ut.image_url == "https://example.com/cover.jpg"

    def test_image_url_none(self, db_session, make_user, make_title) -> None:
        """``image_url`` returns None when title has no image."""
        title = make_title(image_url=None)
        ut = make_user_title_instance(db_session, make_user(), title)

        assert ut.image_url is None

    def test_media_type(self, db_session, make_user, make_title) -> None:
        """``media_type`` proxies ``title.media_type``."""
        title = make_title(media_type="Xbox360Game")
        ut = make_user_title_instance(db_session, make_user(), title)

        assert ut.media_type == "Xbox360Game"

    def test_media_type_none_returns_empty_string(
        self, db_session, make_user, make_title
    ) -> None:
        """``media_type`` returns an empty string when title.media_type is None."""
        title = make_title(media_type=None)
        ut = make_user_title_instance(db_session, make_user(), title)

        assert ut.media_type == ""


class TestUserTitleRepr:
    """Tests for the ``__repr__`` method."""

    def test_repr_format(self, db_session, make_user, make_title) -> None:
        """``__repr__`` includes the title name and progress fraction."""
        title = make_title(name="Dark Souls", total_achievements=20)
        ut = make_user_title_instance(
            db_session, make_user(), title, current_achievements=5
        )

        r = repr(ut)
        assert "Dark Souls" in r
        assert "5/20" in r
        assert "UserTitle" in r


# ------------------------------------------------------------------
# Module-level helper
# ------------------------------------------------------------------


def make_user_title_instance(db_session, user, title, **extra) -> UserTitle:
    """Create, add, and flush a :class:`UserTitle` row."""
    ut = UserTitle(user_id=user.id, title_id=title.id, **extra)
    db_session.add(ut)
    db_session.flush()
    return ut
