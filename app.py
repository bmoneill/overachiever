import os

import requests
from dotenv import load_dotenv
from flask import Flask, flash, redirect, render_template, request, url_for

load_dotenv()

app = Flask(__name__)
app.secret_key = os.urandom(24)

OPENXBL_API_KEY = os.environ.get("OPENXBL_API_KEY")
OPENXBL_BASE_URL = "https://api.xbl.io"


def xbl_get(path):
    """Make an authenticated GET request to the OpenXBL API.

    Returns the unwrapped 'content' payload on success, or None on failure.
    On failure a flash message is set automatically.
    """
    if not OPENXBL_API_KEY:
        flash("OPENXBL_API_KEY is not set. Please add it to your .env file.", "error")
        return None

    headers = {
        "X-Authorization": OPENXBL_API_KEY,
        "Accept": "application/json",
    }

    try:
        resp = requests.get(
            f"{OPENXBL_BASE_URL}{path}",
            headers=headers,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.RequestException as exc:
        if hasattr(exc, "response") and exc.response is not None:
            flash(
                f"OpenXBL returned status {exc.response.status_code}. "
                "Check that the XUID is correct.",
                "error",
            )
        else:
            flash(f"Failed to reach OpenXBL: {exc}", "error")
        return None

    # The OpenXBL API wraps responses in {"content": ..., "code": ...}.
    # Unwrap if present, otherwise return the raw data.
    if isinstance(data, dict) and "content" in data:
        return data["content"]
    return data


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        xuid = request.form.get("xuid", "").strip()
        if not xuid:
            flash("Please enter an XUID.", "error")
            return redirect(url_for("index"))
        return redirect(url_for("games", xuid=xuid))
    return render_template("index.html")


@app.route("/games/<xuid>")
def games(xuid):
    """Show the list of games a player owns with achievement counts."""
    content = xbl_get(f"/v2/titles/{xuid}")
    if content is None:
        return redirect(url_for("index"))

    titles = content.get("titles", []) if isinstance(content, dict) else []

    return render_template("games.html", titles=titles, xuid=xuid)


@app.route("/games/<xuid>/<title_id>")
def game_achievements(xuid, title_id):
    """Show unlocked and locked achievements for a specific game."""
    content = xbl_get(f"/v2/achievements/player/{xuid}/{title_id}")
    if content is None:
        return redirect(url_for("games", xuid=xuid))

    # The response may be a dict with an "achievements" key, or a list directly.
    if isinstance(content, dict):
        achievements = content.get("achievements", [])
    elif isinstance(content, list):
        achievements = content
    else:
        achievements = []

    unlocked = []
    locked = []
    game_name = None

    for a in achievements:
        # Try to grab the game name from the first achievement's titleAssociations
        if game_name is None:
            assocs = a.get("titleAssociations", [])
            if assocs:
                game_name = assocs[0].get("name")

        if a.get("progressState") == "Achieved":
            unlocked.append(a)
        else:
            locked.append(a)

    if game_name is None:
        game_name = f"Title {title_id}"

    return render_template(
        "game_achievements.html",
        unlocked=unlocked,
        locked=locked,
        game_name=game_name,
        xuid=xuid,
        title_id=title_id,
    )


if __name__ == "__main__":
    app.run(debug=True)
