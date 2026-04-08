"""Tests for :mod:`src.api.profile`.

Covers the :class:`Profile` data class (construction, attribute access)
and the :class:`ProfileAPI` abstract base class (interface contract,
cannot be instantiated directly, concrete subclass works).
"""

from __future__ import annotations

import pytest

from src.api.profile import Profile, ProfileAPI, ProfileAPIError

# ------------------------------------------------------------------
# Dummy subclass that satisfies the ABC contract
# ------------------------------------------------------------------


class DummyProfileAPI(ProfileAPI):
    """Minimal concrete implementation used by tests.

    Stores a canned :class:`Profile` that ``get_user_profile`` returns
    for any ``user_id``.
    """

    def __init__(self, profile: Profile | None = None) -> None:
        self._profile = profile

    def get_user_profile(self, user_id: str) -> Profile:
        """Return the canned profile, or raise if none was supplied."""
        if self._profile is None:
            raise ProfileAPIError(f"No profile for user {user_id}")
        return self._profile


class IncompleteProfileAPI(ProfileAPI):
    """Subclass that deliberately does NOT implement the abstract method."""

    pass


# ===================================================================
# Profile tests
# ===================================================================


class TestProfile:
    """Tests for the :class:`Profile` data class."""

    def test_construction_required_fields(self) -> None:
        """Should store ``platform_id`` and ``name`` correctly."""
        profile = Profile(platform_id=1, name="TestUser")
        assert profile.platform_id == 1
        assert profile.name == "TestUser"

    def test_default_image_url(self) -> None:
        """``image_url`` should default to an empty string."""
        profile = Profile(platform_id=2, name="SteamUser")
        assert profile.image_url == ""

    def test_custom_image_url(self) -> None:
        """``image_url`` should accept an explicit value."""
        profile = Profile(
            platform_id=1,
            name="GamerTag",
            image_url="https://example.com/avatar.png",
        )
        assert profile.image_url == "https://example.com/avatar.png"

    def test_attributes_are_mutable(self) -> None:
        """Profile attributes should be freely reassignable."""
        profile = Profile(platform_id=0, name="Old")
        profile.name = "New"
        profile.platform_id = 99
        profile.image_url = "https://new.example.com/pic.jpg"

        assert profile.name == "New"
        assert profile.platform_id == 99
        assert profile.image_url == "https://new.example.com/pic.jpg"

    def test_multiple_instances_independent(self) -> None:
        """Different Profile instances should not share state."""
        p1 = Profile(platform_id=1, name="Alice")
        p2 = Profile(platform_id=2, name="Bob")

        assert p1.name != p2.name
        assert p1.platform_id != p2.platform_id

        p1.name = "Changed"
        assert p2.name == "Bob"


# ===================================================================
# ProfileAPIError tests
# ===================================================================


class TestProfileAPIError:
    """Tests for the :class:`ProfileAPIError` exception."""

    def test_is_exception(self) -> None:
        """Should be a subclass of ``Exception``."""
        assert issubclass(ProfileAPIError, Exception)

    def test_message(self) -> None:
        """Should carry the supplied message."""
        err = ProfileAPIError("user not found")
        assert str(err) == "user not found"

    def test_can_be_raised_and_caught(self) -> None:
        """Should be catchable as ``ProfileAPIError``."""
        with pytest.raises(ProfileAPIError, match="oops"):
            raise ProfileAPIError("oops")


# ===================================================================
# ProfileAPI ABC tests
# ===================================================================


class TestProfileAPIABC:
    """Tests for the :class:`ProfileAPI` abstract base class."""

    def test_cannot_instantiate_directly(self) -> None:
        """Instantiating the ABC without implementing abstract methods
        should raise ``TypeError``."""
        with pytest.raises(TypeError):
            ProfileAPI()  # type: ignore[abstract]

    def test_incomplete_subclass_cannot_instantiate(self) -> None:
        """A subclass that omits the abstract method should also raise."""
        with pytest.raises(TypeError):
            IncompleteProfileAPI()  # type: ignore[abstract]


# ===================================================================
# DummyProfileAPI (concrete subclass) tests
# ===================================================================


class TestDummyProfileAPI:
    """Tests for the concrete subclass to verify the interface contract."""

    def test_returns_profile(self) -> None:
        """``get_user_profile`` should return the canned profile."""
        expected = Profile(
            platform_id=1,
            name="Gamer123",
            image_url="https://img.example.com/1.png",
        )
        api = DummyProfileAPI(profile=expected)

        result = api.get_user_profile("some-user-id")

        assert result is expected
        assert result.platform_id == 1
        assert result.name == "Gamer123"
        assert result.image_url == "https://img.example.com/1.png"

    def test_raises_when_no_profile(self) -> None:
        """Should raise ``ProfileAPIError`` when no canned profile exists."""
        api = DummyProfileAPI(profile=None)

        with pytest.raises(ProfileAPIError, match="No profile for user"):
            api.get_user_profile("unknown-user")

    def test_different_user_ids_return_same_canned_profile(self) -> None:
        """The dummy always returns the same profile regardless of user ID."""
        canned = Profile(platform_id=2, name="SteamPlayer")
        api = DummyProfileAPI(profile=canned)

        assert api.get_user_profile("user-a") is api.get_user_profile("user-b")

    def test_is_instance_of_profile_api(self) -> None:
        """The dummy subclass should be an instance of ``ProfileAPI``."""
        api = DummyProfileAPI()
        assert isinstance(api, ProfileAPI)
