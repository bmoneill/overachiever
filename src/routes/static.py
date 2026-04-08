"""Static files route."""

from flask import make_response, send_from_directory

from .. import app


@app.route("/static/<path:filename>")
def static(filename):
    """Serve static files."""
    resp = make_response(send_from_directory("static/", filename))
    resp.headers["Cache-Control"] = "max-age=1209600"
    return resp
