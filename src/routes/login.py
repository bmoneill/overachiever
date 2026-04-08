from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_user
from werkzeug.security import check_password_hash

from .. import app
from ._helpers import ALLOW_REGISTRATION, get_user_by_username


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("my_games"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            flash("Please fill in all fields.", "error")
            return redirect(url_for("login"))

        user = get_user_by_username(username)
        if user is None or not check_password_hash(
            user.password_hash, password
        ):
            flash("Invalid username or password.", "error")
            return redirect(url_for("login"))

        login_user(user)
        next_page = request.args.get("next")
        return redirect(next_page or url_for("my_games"))

    return render_template("login.html", allow_registration=ALLOW_REGISTRATION)
