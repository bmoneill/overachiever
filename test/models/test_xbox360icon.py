"""Unit tests for the :class:`Xbox360Icon` model."""

from __future__ import annotations

from src.models.xbox360icon import Xbox360Icon


class TestXbox360IconCreation:
    """Tests for basic Xbox360Icon instantiation and column defaults."""

    def test_create_icon(self, make_xbox360icon):
        """An icon can be created with all required fields."""
        icon = make_xbox360icon(
            url="https://example.com/icon.png",
            title_id=42,
            achievement_id=99,
        )

        assert icon.id is not None
        assert icon.url == "https://example.com/icon.png"
        assert icon.title_id == 42
        assert icon.achievement_id == 99

    def test_auto_increment_id(self, make_xbox360icon):
        """Each new icon receives a unique auto-incremented primary key."""
        icon1 = make_xbox360icon()
        icon2 = make_xbox360icon()

        assert icon1.id != icon2.id

    def test_tablename(self):
        """The model maps to the ``xbox360icons`` table."""
        assert Xbox360Icon.__tablename__ == "xbox360icons"


class TestXbox360IconQuery:
    """Tests for querying Xbox360Icon records."""

    def test_query_by_title_id(self, db_session, make_xbox360icon):
        """Icons can be filtered by ``title_id``."""
        make_xbox360icon(title_id=10, achievement_id=1)
        make_xbox360icon(title_id=10, achievement_id=2)
        make_xbox360icon(title_id=20, achievement_id=3)

        results = Xbox360Icon.query.filter_by(title_id=10).all()

        assert len(results) == 2

    def test_query_by_achievement_id(self, db_session, make_xbox360icon):
        """Icons can be filtered by ``achievement_id``."""
        make_xbox360icon(title_id=10, achievement_id=5)
        make_xbox360icon(title_id=20, achievement_id=5)
        make_xbox360icon(title_id=30, achievement_id=6)

        results = Xbox360Icon.query.filter_by(achievement_id=5).all()

        assert len(results) == 2

    def test_query_by_title_and_achievement(self, db_session, make_xbox360icon):
        """Icons can be filtered by both ``title_id`` and ``achievement_id``."""
        target = make_xbox360icon(title_id=10, achievement_id=5)
        make_xbox360icon(title_id=10, achievement_id=6)
        make_xbox360icon(title_id=20, achievement_id=5)

        results = Xbox360Icon.query.filter_by(
            title_id=10, achievement_id=5
        ).all()

        assert len(results) == 1
        assert results[0].id == target.id


class TestXbox360IconColumns:
    """Tests verifying column presence and types."""

    def test_url_stored_correctly(self, db_session, make_xbox360icon):
        """The ``url`` column stores the full URL string."""
        url = "https://image.xboxlive.com/global/t.58480800/ach/0/10"
        icon = make_xbox360icon(url=url)

        fetched = db_session.get(Xbox360Icon, icon.id)

        assert fetched.url == url

    def test_integer_fields(self, db_session, make_xbox360icon):
        """``title_id`` and ``achievement_id`` are stored as integers."""
        icon = make_xbox360icon(title_id=999, achievement_id=888)

        fetched = db_session.get(Xbox360Icon, icon.id)

        assert isinstance(fetched.title_id, int)
        assert isinstance(fetched.achievement_id, int)
