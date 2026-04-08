"""Unit tests for the :class:`~src.models.guide.Guide` model."""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError

from src.models.guide import Guide


class TestGuideCreation:
    """Tests for basic Guide instantiation and column defaults."""

    def test_create_guide_with_required_fields(
        self, db_session, make_guide
    ) -> None:
        """A guide can be created with only the required fields."""
        guide = make_guide()
        assert guide.id is not None
        assert guide.url is not None
        assert guide.platform_id is not None
        assert guide.title_id is not None

    def test_url_is_required(
        self, db_session, make_user, make_achievement
    ) -> None:
        """Creating a guide without a URL should raise an IntegrityError."""
        user = make_user()
        achievement = make_achievement()
        guide = Guide(
            url=None,
            platform_id=1,
            title_id=str(achievement.title_id),
            achievement_id=achievement.id,
            user_id=user.id,
        )
        db_session.add(guide)
        with pytest.raises(IntegrityError):
            db_session.flush()

    def test_platform_id_is_required(
        self, db_session, make_user, make_achievement
    ) -> None:
        """Creating a guide without a platform_id should raise an IntegrityError."""
        user = make_user()
        achievement = make_achievement()
        guide = Guide(
            url="https://example.com/guide",
            platform_id=None,
            title_id=str(achievement.title_id),
            achievement_id=achievement.id,
            user_id=user.id,
        )
        db_session.add(guide)
        with pytest.raises(IntegrityError):
            db_session.flush()

    def test_title_id_column_is_required(
        self, db_session, make_user, make_achievement
    ) -> None:
        """Creating a guide without a title_id should raise an IntegrityError."""
        user = make_user()
        achievement = make_achievement()
        guide = Guide(
            url="https://example.com/guide",
            platform_id=1,
            title_id=None,
            achievement_id=achievement.id,
            user_id=user.id,
        )
        db_session.add(guide)
        with pytest.raises(IntegrityError):
            db_session.flush()

    def test_optional_fields_default_to_none(self, db_session) -> None:
        """Optional columns should default to ``None``."""
        guide = Guide(
            url="https://example.com/guide",
            platform_id=1,
            title_id="123",
        )
        db_session.add(guide)
        db_session.flush()

        assert guide.title is None
        assert guide.description is None
        assert guide.achievement_id is None
        assert guide.user_id is None

    def test_title_and_description_stored(self, db_session, make_guide) -> None:
        """The ``title`` and ``description`` text fields are stored correctly."""
        guide = make_guide(title="How to unlock X", description="Step-by-step")
        db_session.commit()

        fetched = db_session.get(Guide, guide.id)
        assert fetched.title == "How to unlock X"
        assert fetched.description == "Step-by-step"

    def test_created_at_has_server_default(
        self, db_session, make_guide
    ) -> None:
        """The ``created_at`` column should be populated automatically."""
        guide = make_guide()
        db_session.commit()

        fetched = db_session.get(Guide, guide.id)
        assert fetched.created_at is not None


class TestGuideRelationships:
    """Tests for Guide relationships and back-references."""

    def test_achievement_relationship(
        self, db_session, make_achievement, make_user
    ) -> None:
        """A guide should reference its associated achievement."""
        achievement = make_achievement()
        user = make_user()
        guide = Guide(
            url="https://example.com/g",
            platform_id=1,
            title_id=str(achievement.title_id),
            achievement_id=achievement.id,
            user_id=user.id,
        )
        db_session.add(guide)
        db_session.flush()

        assert guide.achievement is not None
        assert guide.achievement.id == achievement.id

    def test_user_relationship(
        self, db_session, make_user, make_achievement
    ) -> None:
        """A guide should reference its associated user."""
        user = make_user(username="author1")
        achievement = make_achievement()
        guide = Guide(
            url="https://example.com/g",
            platform_id=1,
            title_id=str(achievement.title_id),
            achievement_id=achievement.id,
            user_id=user.id,
        )
        db_session.add(guide)
        db_session.flush()

        assert guide.user is not None
        assert guide.user.username == "author1"

    def test_achievement_backref_guides(
        self, db_session, make_achievement, make_user
    ) -> None:
        """The achievement's ``guides`` backref should include the guide."""
        achievement = make_achievement()
        user = make_user()
        guide = Guide(
            url="https://example.com/g",
            platform_id=1,
            title_id=str(achievement.title_id),
            achievement_id=achievement.id,
            user_id=user.id,
        )
        db_session.add(guide)
        db_session.flush()

        assert guide in achievement.guides.all()

    def test_user_backref_guides(
        self, db_session, make_user, make_achievement
    ) -> None:
        """The user's ``guides`` backref should include the guide."""
        user = make_user()
        achievement = make_achievement()
        guide = Guide(
            url="https://example.com/g",
            platform_id=1,
            title_id=str(achievement.title_id),
            achievement_id=achievement.id,
            user_id=user.id,
        )
        db_session.add(guide)
        db_session.flush()

        assert guide in user.guides.all()


class TestGuideConvenienceProperties:
    """Tests for the convenience properties on Guide."""

    def test_author_returns_username(
        self, db_session, make_guide, make_user
    ) -> None:
        """``author`` should return the related user's username."""
        user = make_user(username="writer99")
        guide = make_guide(user=user)

        assert guide.author == "writer99"

    def test_author_returns_none_when_no_user(self, db_session) -> None:
        """``author`` should return ``None`` when no user is associated."""
        guide = Guide(
            url="https://example.com/g",
            platform_id=1,
            title_id="42",
        )
        db_session.add(guide)
        db_session.flush()

        assert guide.author is None

    def test_game_name_traverses_achievement_title(
        self, db_session, make_title, make_achievement, make_user
    ) -> None:
        """``game_name`` should return the title name via achievement."""
        title = make_title(name="Halo Infinite")
        achievement = make_achievement(title=title)
        user = make_user()
        guide = Guide(
            url="https://example.com/g",
            platform_id=1,
            title_id=str(title.id),
            achievement_id=achievement.id,
            user_id=user.id,
        )
        db_session.add(guide)
        db_session.flush()

        assert guide.game_name == "Halo Infinite"

    def test_game_name_returns_none_without_achievement(
        self, db_session
    ) -> None:
        """``game_name`` should return ``None`` when there is no achievement."""
        guide = Guide(
            url="https://example.com/g",
            platform_id=1,
            title_id="42",
        )
        db_session.add(guide)
        db_session.flush()

        assert guide.game_name is None

    def test_achievement_name_property(
        self, db_session, make_achievement, make_user
    ) -> None:
        """``achievement_name`` should return the achievement's name."""
        achievement = make_achievement(achievement_name="First Blood")
        user = make_user()
        guide = Guide(
            url="https://example.com/g",
            platform_id=1,
            title_id=str(achievement.title_id),
            achievement_id=achievement.id,
            user_id=user.id,
        )
        db_session.add(guide)
        db_session.flush()

        assert guide.achievement_name == "First Blood"

    def test_achievement_name_returns_none_without_achievement(
        self, db_session
    ) -> None:
        """``achievement_name`` should be ``None`` when no achievement is set."""
        guide = Guide(
            url="https://example.com/g",
            platform_id=1,
            title_id="42",
        )
        db_session.add(guide)
        db_session.flush()

        assert guide.achievement_name is None

    def test_achievement_description_property(
        self, db_session, make_achievement, make_user
    ) -> None:
        """``achievement_description`` should return the achievement's description."""
        achievement = make_achievement(description="Get the first kill")
        user = make_user()
        guide = Guide(
            url="https://example.com/g",
            platform_id=1,
            title_id=str(achievement.title_id),
            achievement_id=achievement.id,
            user_id=user.id,
        )
        db_session.add(guide)
        db_session.flush()

        assert guide.achievement_description == "Get the first kill"

    def test_achievement_description_returns_none_without_achievement(
        self, db_session
    ) -> None:
        """``achievement_description`` should be ``None`` when no achievement."""
        guide = Guide(
            url="https://example.com/g",
            platform_id=1,
            title_id="42",
        )
        db_session.add(guide)
        db_session.flush()

        assert guide.achievement_description is None
