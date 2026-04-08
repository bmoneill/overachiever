"""Unit tests for the :class:`Achievement` model."""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError

from src.models.achievement import Achievement
from src.models.title import Title


class TestAchievementCreation:
    """Tests for basic Achievement instantiation and persistence."""

    def test_create_achievement_with_required_fields(
        self, db_session, make_title
    ):
        """An achievement can be created with only required fields."""
        title = make_title()
        ach = Achievement(
            achievement_id="1",
            title_id=title.id,
            achievement_name="First Blood",
        )
        db_session.add(ach)
        db_session.flush()

        assert ach.id is not None
        assert ach.achievement_id == "1"
        assert ach.title_id == title.id
        assert ach.achievement_name == "First Blood"

    def test_optional_fields_default_to_none(self, db_session, make_title):
        """Optional columns default to ``None`` when not provided."""
        title = make_title()
        ach = Achievement(
            achievement_id="2",
            title_id=title.id,
            achievement_name="Optional Test",
        )
        db_session.add(ach)
        db_session.flush()

        assert ach.description is None
        assert ach.locked_description is None
        assert ach.gamerscore is None
        assert ach.rarity is None
        assert ach.image_url is None

    def test_create_achievement_with_all_fields(self, db_session, make_title):
        """An achievement can be created with every column populated."""
        title = make_title()
        ach = Achievement(
            achievement_id="3",
            title_id=title.id,
            achievement_name="Full Load",
            description="Unlock everything.",
            locked_description="Keep playing.",
            gamerscore=50,
            rarity=12.5,
            image_url="https://example.com/img.png",
        )
        db_session.add(ach)
        db_session.flush()

        assert ach.description == "Unlock everything."
        assert ach.locked_description == "Keep playing."
        assert ach.gamerscore == 50
        assert ach.rarity == pytest.approx(12.5)
        assert ach.image_url == "https://example.com/img.png"

    def test_achievement_id_not_nullable(self, db_session, make_title):
        """``achievement_id`` must not be null."""
        title = make_title()
        ach = Achievement(
            achievement_id=None,
            title_id=title.id,
            achievement_name="Broken",
        )
        db_session.add(ach)
        with pytest.raises(IntegrityError):
            db_session.flush()

    def test_achievement_name_not_nullable(self, db_session, make_title):
        """``achievement_name`` must not be null."""
        title = make_title()
        ach = Achievement(
            achievement_id="99",
            title_id=title.id,
            achievement_name=None,
        )
        db_session.add(ach)
        with pytest.raises(IntegrityError):
            db_session.flush()


class TestAchievementUniqueConstraint:
    """Tests for the ``uq_achievement_identity`` unique constraint."""

    def test_duplicate_achievement_for_same_title_raises(
        self, db_session, make_title
    ):
        """Two achievements with the same title_id + achievement_id must fail."""
        title = make_title()
        ach1 = Achievement(
            achievement_id="DUP",
            title_id=title.id,
            achievement_name="First",
        )
        ach2 = Achievement(
            achievement_id="DUP",
            title_id=title.id,
            achievement_name="Second",
        )
        db_session.add_all([ach1, ach2])
        with pytest.raises(IntegrityError):
            db_session.flush()

    def test_same_achievement_id_different_titles_allowed(
        self, db_session, make_title
    ):
        """The same ``achievement_id`` under different titles is allowed."""
        title_a = make_title(name="Game A", platform_title_id="200")
        title_b = make_title(name="Game B", platform_title_id="201")
        ach1 = Achievement(
            achievement_id="SHARED",
            title_id=title_a.id,
            achievement_name="A version",
        )
        ach2 = Achievement(
            achievement_id="SHARED",
            title_id=title_b.id,
            achievement_name="B version",
        )
        db_session.add_all([ach1, ach2])
        db_session.flush()

        assert ach1.id != ach2.id


class TestAchievementRelationship:
    """Tests for the Achievement ↔ Title relationship."""

    def test_title_relationship(self, db_session, make_achievement):
        """An achievement should expose its parent title via ``title``."""
        ach = make_achievement()
        assert ach.title is not None
        assert isinstance(ach.title, Title)

    def test_title_back_populates(self, db_session, make_title):
        """A title's ``achievements`` collection should include its children."""
        title = make_title()
        ach = Achievement(
            achievement_id="BP1",
            title_id=title.id,
            achievement_name="Back-pop test",
        )
        db_session.add(ach)
        db_session.flush()

        assert ach in title.achievements.all()


class TestAchievementProxyProperties:
    """Tests for convenience properties that proxy through the title."""

    def test_platform_id_returns_title_platform(self, db_session, make_title):
        """``platform_id`` should return the title's platform integer."""
        title = make_title(platform=2)
        ach = Achievement(
            achievement_id="P1",
            title_id=title.id,
            achievement_name="Platform test",
        )
        db_session.add(ach)
        db_session.flush()

        assert ach.platform_id == 2

    def test_platform_id_returns_none_without_title(self):
        """``platform_id`` returns ``None`` when the title is not loaded."""
        ach = Achievement(
            achievement_id="X",
            achievement_name="Detached",
        )
        assert ach.platform_id is None

    def test_platform_title_id_returns_title_value(
        self, db_session, make_title
    ):
        """``platform_title_id`` proxies ``title.platform_title_id``."""
        title = make_title(platform_title_id="ABCD")
        ach = Achievement(
            achievement_id="P2",
            title_id=title.id,
            achievement_name="PlatformTitleId test",
        )
        db_session.add(ach)
        db_session.flush()

        assert ach.platform_title_id == "ABCD"

    def test_platform_title_id_returns_none_without_title(self):
        """``platform_title_id`` returns ``None`` when title is absent."""
        ach = Achievement(
            achievement_id="X",
            achievement_name="Detached",
        )
        assert ach.platform_title_id is None

    def test_game_name_returns_title_name(self, db_session, make_title):
        """``game_name`` proxies ``title.name``."""
        title = make_title(name="Halo Infinite")
        ach = Achievement(
            achievement_id="GN1",
            title_id=title.id,
            achievement_name="Game name test",
        )
        db_session.add(ach)
        db_session.flush()

        assert ach.game_name == "Halo Infinite"

    def test_game_name_returns_none_without_title(self):
        """``game_name`` returns ``None`` when the title is absent."""
        ach = Achievement(
            achievement_id="X",
            achievement_name="Detached",
        )
        assert ach.game_name is None

    def test_platform_xbox(self, db_session, make_title):
        """``platform`` returns ``'xbox'`` for platform ID 1."""
        title = make_title(platform=1)
        ach = Achievement(
            achievement_id="XB",
            title_id=title.id,
            achievement_name="Xbox test",
        )
        db_session.add(ach)
        db_session.flush()

        assert ach.platform == "xbox"

    def test_platform_steam(self, db_session, make_title):
        """``platform`` returns ``'steam'`` for platform ID 2."""
        title = make_title(platform=2, platform_title_id="STEAM1")
        ach = Achievement(
            achievement_id="ST",
            title_id=title.id,
            achievement_name="Steam test",
        )
        db_session.add(ach)
        db_session.flush()

        assert ach.platform == "steam"

    def test_platform_psn(self, db_session, make_title):
        """``platform`` returns ``'psn'`` for platform ID 0."""
        title = make_title(platform=0, platform_title_id="PSN1")
        ach = Achievement(
            achievement_id="PS",
            title_id=title.id,
            achievement_name="PSN test",
        )
        db_session.add(ach)
        db_session.flush()

        assert ach.platform == "psn"

    def test_platform_unknown_for_unmapped_id(self, db_session, make_title):
        """``platform`` returns ``'unknown'`` for an unmapped platform ID."""
        title = make_title(platform=999, platform_title_id="UNK1")
        ach = Achievement(
            achievement_id="UK",
            title_id=title.id,
            achievement_name="Unknown platform",
        )
        db_session.add(ach)
        db_session.flush()

        assert ach.platform == "unknown"

    def test_platform_unknown_without_title(self):
        """``platform`` returns ``'unknown'`` when the title is absent."""
        ach = Achievement(
            achievement_id="X",
            achievement_name="Detached",
        )
        assert ach.platform == "unknown"


class TestAchievementTemplateAliases:
    """Tests for the ``name`` and ``rarity_percentage`` template aliases."""

    def test_name_getter(self, db_session, make_achievement):
        """``name`` returns ``achievement_name``."""
        ach = make_achievement(achievement_name="Foo")
        assert ach.name == "Foo"

    def test_name_setter(self, db_session, make_achievement):
        """Setting ``name`` mutates ``achievement_name``."""
        ach = make_achievement()
        ach.name = "Renamed"
        assert ach.achievement_name == "Renamed"

    def test_rarity_percentage_getter(self, db_session, make_title):
        """``rarity_percentage`` returns ``rarity``."""
        title = make_title()
        ach = Achievement(
            achievement_id="RP1",
            title_id=title.id,
            achievement_name="Rare one",
            rarity=5.5,
        )
        db_session.add(ach)
        db_session.flush()

        assert ach.rarity_percentage == pytest.approx(5.5)

    def test_rarity_percentage_setter(self, db_session, make_achievement):
        """Setting ``rarity_percentage`` mutates ``rarity``."""
        ach = make_achievement()
        ach.rarity_percentage = 99.9
        assert ach.rarity == pytest.approx(99.9)

    def test_rarity_percentage_none(self, db_session, make_achievement):
        """``rarity_percentage`` is ``None`` when ``rarity`` is not set."""
        ach = make_achievement()
        assert ach.rarity_percentage is None


class TestAchievementFindByPlatform:
    """Tests for the ``find_by_platform`` class method."""

    def test_find_existing_achievement(self, db_session, make_title):
        """``find_by_platform`` returns the matching achievement."""
        title = make_title(platform=1, platform_title_id="T100")
        ach = Achievement(
            achievement_id="A1",
            title_id=title.id,
            achievement_name="Findable",
        )
        db_session.add(ach)
        db_session.flush()

        result = Achievement.find_by_platform(1, "T100", "A1")
        assert result is not None
        assert result.id == ach.id

    def test_find_returns_none_for_missing(self, db_session, make_title):
        """``find_by_platform`` returns ``None`` when no match exists."""
        make_title(platform=1, platform_title_id="T200")
        result = Achievement.find_by_platform(1, "T200", "MISSING")
        assert result is None

    def test_find_wrong_platform(self, db_session, make_title):
        """``find_by_platform`` does not match a different platform."""
        title = make_title(platform=1, platform_title_id="T300")
        ach = Achievement(
            achievement_id="A3",
            title_id=title.id,
            achievement_name="Xbox only",
        )
        db_session.add(ach)
        db_session.flush()

        result = Achievement.find_by_platform(2, "T300", "A3")
        assert result is None
