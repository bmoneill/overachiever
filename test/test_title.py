"""Unit tests for the :class:`~src.models.title.Title` model."""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError

from src.models.title import Title


class TestTitleCreation:
    """Tests for basic Title instantiation and column defaults."""

    def test_create_title_with_required_fields(self, db_session, make_title):
        """A title can be created with only the required fields."""
        title = make_title(
            name="Halo 3",
            platform=1,
            platform_title_id="12345",
        )

        assert title.id is not None
        assert title.name == "Halo 3"
        assert title.platform == 1
        assert title.platform_title_id == "12345"

    def test_default_total_achievements_is_zero(self, db_session, make_title):
        """``total_achievements`` should default to 0 when not specified."""
        title = make_title()

        assert title.total_achievements == 0 or title.total_achievements == 10
        # The factory sets a default of 10; test the raw default instead.
        raw = Title(
            name="Test",
            platform=1,
            platform_title_id="99999",
        )
        db_session.add(raw)
        db_session.flush()
        assert raw.total_achievements == 0

    def test_optional_fields_default_to_none(self, db_session):
        """``image_url`` and ``media_type`` should default to ``None``."""
        title = Title(
            name="Portal 2",
            platform=2,
            platform_title_id="620",
        )
        db_session.add(title)
        db_session.flush()

        assert title.image_url is None
        assert title.media_type is None

    def test_create_title_with_all_fields(self, db_session):
        """A title can be created with every column populated."""
        title = Title(
            name="Dark Souls",
            platform=1,
            platform_title_id="55555",
            image_url="https://example.com/ds.jpg",
            media_type="Xbox360Game",
            total_achievements=41,
        )
        db_session.add(title)
        db_session.flush()

        assert title.image_url == "https://example.com/ds.jpg"
        assert title.media_type == "Xbox360Game"
        assert title.total_achievements == 41


class TestTitleConstraints:
    """Tests for table-level constraints."""

    def test_unique_platform_and_platform_title_id(
        self, db_session, make_title
    ):
        """Inserting two titles with the same platform+platform_title_id raises."""
        make_title(platform=1, platform_title_id="DUP")

        with pytest.raises(IntegrityError):
            make_title(platform=1, platform_title_id="DUP")

    def test_different_platforms_same_title_id_allowed(
        self, db_session, make_title
    ):
        """The same platform_title_id on *different* platforms is allowed."""
        t1 = make_title(platform=1, platform_title_id="SHARED")
        t2 = make_title(platform=2, platform_title_id="SHARED")

        assert t1.id != t2.id

    def test_name_not_nullable(self, db_session):
        """``name`` is required — omitting it should raise."""
        title = Title(platform=1, platform_title_id="NONAME")
        db_session.add(title)

        with pytest.raises(IntegrityError):
            db_session.flush()

    def test_platform_not_nullable(self, db_session):
        """``platform`` is required — omitting it should raise."""
        title = Title(name="Test", platform_title_id="NOPLAT")
        db_session.add(title)

        with pytest.raises(IntegrityError):
            db_session.flush()

    def test_platform_title_id_not_nullable(self, db_session):
        """``platform_title_id`` is required — omitting it should raise."""
        title = Title(name="Test", platform=1)
        db_session.add(title)

        with pytest.raises(IntegrityError):
            db_session.flush()


class TestTitleRelationships:
    """Tests for the ``achievements`` relationship."""

    def test_achievements_relationship_initially_empty(
        self, db_session, make_title
    ):
        """A new title starts with an empty achievements collection."""
        title = make_title()

        assert title.achievements.count() == 0

    def test_achievements_back_populates(
        self, db_session, make_title, make_achievement
    ):
        """Achievements added via the factory are visible through the relationship."""
        title = make_title()
        ach = make_achievement(title=title)

        assert title.achievements.count() == 1
        assert title.achievements.first().id == ach.id


class TestFindByPlatform:
    """Tests for :meth:`Title.find_by_platform`."""

    def test_returns_matching_title(self, db_session, make_title):
        """``find_by_platform`` returns the correct title."""
        title = make_title(platform=2, platform_title_id="440")

        result = Title.find_by_platform(2, 440)

        assert result is not None
        assert result.id == title.id

    def test_returns_none_when_not_found(self, db_session, make_title):
        """``find_by_platform`` returns ``None`` when no match exists."""
        make_title(platform=1, platform_title_id="111")

        result = Title.find_by_platform(2, 999)

        assert result is None


class TestTitleRepr:
    """Tests for the ``__repr__`` method."""

    def test_repr_contains_key_fields(self, db_session, make_title):
        """``__repr__`` includes the id, name, platform, and platform_title_id."""
        title = make_title(
            name="Celeste",
            platform=2,
            platform_title_id="504230",
        )
        representation = repr(title)

        assert "Title" in representation
        assert "Celeste" in representation
        assert "504230" in representation
        assert str(title.id) in representation
