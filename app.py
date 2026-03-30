import os

import requests
from dotenv import load_dotenv
from flask import Flask, flash, redirect, render_template, request, url_for

load_dotenv()

app = Flask(__name__)
app.secret_key = os.urandom(24)

OPENXBL_API_KEY = os.environ.get("OPENXBL_API_KEY")
OPENXBL_BASE_URL = "https://xbl.io/api/v2"


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        xuid = request.form.get("xuid", "").strip()
        if not xuid:
            flash("Please enter an XUID.", "error")
            return redirect(url_for("index"))
        return redirect(url_for("achievements", xuid=xuid))
    return render_template("index.html")


@app.route("/achievements/<xuid>")
def achievements(xuid):
    if not OPENXBL_API_KEY:
        flash("OPENXBL_API_KEY is not set. Please add it to your .env file.", "error")
        return redirect(url_for("index"))

    headers = {
        "X-Authorization": OPENXBL_API_KEY,
        "Accept": "application/json",
    }

    try:
        resp = requests.get(
            f"{OPENXBL_BASE_URL}/achievements/player/{xuid}",
            headers=headers,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.RequestException as exc:
        if hasattr(exc, "response") and exc.response is not None:
            flash(
                f"OpenXBL returned status {exc.response.status_code}. Check that the XUID is correct.",
                "error",
            )
        else:
            flash(f"Failed to reach OpenXBL: {exc}", "error")
        return redirect(url_for("index"))

    titles = data if isinstance(data, list) else data.get("titles", [])

    return render_template("achievements.html", titles=titles, xuid=xuid)


if __name__ == "__main__":
    app.run(debug=True)
