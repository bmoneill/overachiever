"""Routes package."""

# Import all route sub-modules to register their @app.route decorators.
from . import (  # noqa: F401
    _helpers,
    all_games,
    favicon,
    games,
    guide_rating_routes,
    guides,
    index,
    login,
    logout,
    my_games,
    profile,
    register,
    search,
    settings,
    showcase,
    static,
    timeline,
    verify_email,
)
