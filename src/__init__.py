import os

from flask import Flask
from flask_login import LoginManager
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or os.urandom(24)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.login_message = "Please log in to access this page."
login_manager.login_message_category = "error"

# Import sub-modules AFTER app and login_manager are created.
# Each module uses `from . import app` / `from . import login_manager`
# to register route decorators and callbacks on the already-created
# instances, avoiding circular-import issues.
from . import db, auth, routes, settings, profile, public_guides  # noqa: E402, F401

app.teardown_appcontext(db.close_db)

with app.app_context():
    db.init_db()
