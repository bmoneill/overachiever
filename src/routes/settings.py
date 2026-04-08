from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from .. import app
from ..api.profile import ProfileAPIError
from ..api.steam import SteamProfileAPI
from ..api.xbox import XboxProfileAPI
from ..models import db
from ..models.user import User


@app.route("/settings")
@login_required
def settings():
    """User settings page with linked platform accounts."""
    xbox_profile = None
    if current_user.xuid:
        try:
            api = XboxProfileAPI()
            xbox_profile = api.get_user_profile(current_user.xuid)
        except ProfileAPIError:
            print("Some error occurred while fetching the Xbox profile.")
            pass

    steam_profile = None
    if current_user.steam_id:
        try:
            api = SteamProfileAPI()
            steam_profile = api.get_user_profile(current_user.steam_id)
        except ProfileAPIError:
            pass

    return render_template(
        "settings.html",
        xbox_profile=xbox_profile,
        steam_profile=steam_profile,
    )


@app.route("/settings/xbox/link", methods=["POST"])
@login_required
def xbox_link():
    """Link an Xbox account by manually entering a XUID."""
    xuid = request.form.get("xuid", "").strip()
    if not xuid:
        flash("Please enter a valid XUID.", "error")
        return redirect(url_for("settings"))

    if current_user.xuid:
        flash("Your Xbox account is already linked.", "error")
        return redirect(url_for("settings"))

    if not xuid.isdigit():
        flash("XUID must be a numeric value.", "error")
        return redirect(url_for("settings"))

    existing = User.query.filter(
        User.xuid == xuid, User.id != current_user.id
    ).first()
    if existing:
        flash("This Xbox account is already linked to another user.", "error")
        return redirect(url_for("settings"))

    current_user.xuid = xuid
    db.session.commit()

    flash("Xbox account linked successfully!", "success")
    return redirect(url_for("settings"))


@app.route("/settings/xbox/unlink", methods=["POST"])
@login_required
def xbox_unlink():
    """Unlink the user's Xbox account (set XUID to NULL)."""
    current_user.xuid = None
    db.session.commit()
    flash("Xbox account unlinked.", "success")
    return redirect(url_for("settings"))


@app.route("/settings/steam/link", methods=["POST"])
@login_required
def steam_link():
    """Link a Steam account by Steam ID or vanity URL."""
    input_type = request.form.get("steam_input_type", "steam_id").strip()
    steam_input = request.form.get("steam_input", "").strip()

    if not steam_input:
        flash("Please enter a Steam ID or vanity URL.", "error")
        return redirect(url_for("settings"))

    if current_user.steam_id:
        flash("Your Steam account is already linked.", "error")
        return redirect(url_for("settings"))

    if input_type == "steam_id":
        if not steam_input.isdigit():
            flash("Steam ID must be a numeric value.", "error")
            return redirect(url_for("settings"))
        steam_id = steam_input
    else:
        try:
            api = SteamProfileAPI()
            steam_id = api.resolve_vanity_url(steam_input)
        except ProfileAPIError as exc:
            flash(f"Could not resolve Steam username: {exc}", "error")
            return redirect(url_for("settings"))

    existing = User.query.filter(
        User.steam_id == steam_id, User.id != current_user.id
    ).first()
    if existing:
        flash("This Steam account is already linked to another user.", "error")
        return redirect(url_for("settings"))

    current_user.steam_id = steam_id
    db.session.commit()

    flash("Steam account linked successfully!", "success")
    return redirect(url_for("settings"))


@app.route("/settings/steam/unlink", methods=["POST"])
@login_required
def steam_unlink():
    """Unlink the user's Steam account (set steam_id to NULL)."""
    current_user.steam_id = None
    db.session.commit()
    flash("Steam account unlinked.", "success")
    return redirect(url_for("settings"))
