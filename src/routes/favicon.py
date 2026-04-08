"""Favicon route."""

import os

from flask import send_from_directory

from .. import app


@app.route("/favicon.ico")
def favicon():
    """Serve the favicon.ico file."""
    return send_from_directory(
        os.path.join(app.root_path, "static"),
        "favicon.ico",
        mimetype="image/vnd.microsoft.icon",
    )
