# Import all route sub-modules to register their @app.route decorators.
from . import (  # noqa: F401
    _helpers,
    index,
    search,
    login,
    register,
    logout,
    my_games,
    games,
    settings,
    showcase,
    profile,
    guides,
)
