from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

from .user import User  # noqa: E402, F401
from .achievement import Achievement  # noqa: E402, F401
from .user_achievement import UserAchievement  # noqa: E402, F401
from .guide import Guide  # noqa: E402, F401
from .guide_rating import GuideRating  # noqa: E402, F401
from .pinned_achievement import PinnedAchievement  # noqa: E402, F401
from .showcase_game import ShowcaseGame  # noqa: E402, F401
from .showcase_achievement import ShowcaseAchievement  # noqa: E402, F401
from .xbox360icon import Xbox360Icon  # noqa: E402, F401
from .user_follow import UserFollow  # noqa: E402, F401
