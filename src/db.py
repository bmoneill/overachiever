import os

from .models import db

_APP_DIR = os.path.dirname(os.path.abspath(__file__))

DATABASE = os.environ.get(
    "DATABASE",
    os.path.join(_APP_DIR, "..", "overachiever.db"),
)


def init_app(app):
    """Configure SQLAlchemy on the Flask application and create tables."""
    app.config.setdefault(
        "SQLALCHEMY_DATABASE_URI",
        f"sqlite:///{os.path.abspath(DATABASE)}",
    )
    app.config.setdefault("SQLALCHEMY_TRACK_MODIFICATIONS", False)

    db.init_app(app)

    with app.app_context():
        _migrate_legacy_tables()
        db.create_all()


def _migrate_legacy_tables():
    """Handle one-time migrations for databases created before SQLAlchemy.

    * Renames the old ``achievement_summaries`` table to
      ``_achievement_summaries_backup`` so its data is preserved but it
      no longer conflicts with the ``achievements`` table that now
      serves both purposes.
    * Adds the ``achievement_id`` column to ``guides`` if it is missing
      and migrates data from the legacy ``achievement_summary_id``
      column by copying matching rows into the ``achievements`` table.
    * Adds any missing columns that were introduced after the original
      schema (e.g. ``achievement_count`` on ``users``).
    """
    from sqlalchemy import inspect, text

    bind = db.engine
    inspector = inspect(bind)
    existing_tables = inspector.get_table_names()

    with bind.connect() as conn:
        # ------------------------------------------------------------------
        # 1. Rename legacy achievement_summaries → _achievement_summaries_backup
        # ------------------------------------------------------------------
        has_summaries_backup = "_achievement_summaries_backup" in existing_tables
        if "achievement_summaries" in existing_tables:
            conn.execute(
                text(
                    "ALTER TABLE achievement_summaries "
                    "RENAME TO _achievement_summaries_backup"
                )
            )
            conn.commit()
            has_summaries_backup = True
            # Refresh table list after rename
            inspector = inspect(bind)
            existing_tables = inspector.get_table_names()

        # ------------------------------------------------------------------
        # 2. Ensure guides.achievement_id exists and migrate from the
        #    legacy achievement_summary_id column if present.
        # ------------------------------------------------------------------
        if "guides" in existing_tables:
            guide_cols = {
                col["name"] for col in inspector.get_columns("guides")
            }

            has_old_col = "achievement_summary_id" in guide_cols
            has_new_col = "achievement_id" in guide_cols

            if not has_new_col:
                conn.execute(
                    text(
                        "ALTER TABLE guides "
                        "ADD COLUMN achievement_id INTEGER DEFAULT NULL "
                        "REFERENCES achievements(id)"
                    )
                )
                conn.commit()

            # Migrate data: for each guide row that references the old
            # achievement_summaries table, ensure a matching row exists
            # in the achievements table and point the new FK there.
            if has_old_col and has_summaries_backup:
                # Fetch all distinct summary IDs referenced by guides
                rows = conn.execute(
                    text(
                        "SELECT DISTINCT g.achievement_summary_id, "
                        "       s.platform_id, s.title_id, s.achievement_id, "
                        "       s.game_name, s.achievement_name, "
                        "       s.achievement_description "
                        "FROM guides g "
                        "JOIN _achievement_summaries_backup s "
                        "  ON s.id = g.achievement_summary_id "
                        "WHERE g.achievement_summary_id IS NOT NULL"
                    )
                ).fetchall()

                for row in rows:
                    (
                        old_summary_id,
                        platform_id,
                        title_id,
                        achievement_id_val,
                        game_name,
                        achievement_name,
                        achievement_description,
                    ) = row

                    # Check if an achievements row already exists for
                    # this (platform_id, title_id, achievement_id) triple.
                    existing = conn.execute(
                        text(
                            "SELECT id FROM achievements "
                            "WHERE platform_id = :pid "
                            "  AND title_id = :tid "
                            "  AND achievement_id = :aid"
                        ),
                        {
                            "pid": platform_id,
                            "tid": str(title_id),
                            "aid": str(achievement_id_val),
                        },
                    ).fetchone()

                    if existing:
                        new_ach_id = existing[0]
                    else:
                        # Insert a new achievement row from the summary data
                        conn.execute(
                            text(
                                "INSERT INTO achievements "
                                "(platform_id, title_id, achievement_id, "
                                " game_name, achievement_name, description) "
                                "VALUES (:pid, :tid, :aid, :gname, :aname, :desc)"
                            ),
                            {
                                "pid": platform_id,
                                "tid": str(title_id),
                                "aid": str(achievement_id_val),
                                "gname": game_name or "Unknown",
                                "aname": achievement_name or "Unknown",
                                "desc": achievement_description,
                            },
                        )
                        new_row = conn.execute(
                            text(
                                "SELECT id FROM achievements "
                                "WHERE platform_id = :pid "
                                "  AND title_id = :tid "
                                "  AND achievement_id = :aid"
                            ),
                            {
                                "pid": platform_id,
                                "tid": str(title_id),
                                "aid": str(achievement_id_val),
                            },
                        ).fetchone()
                        new_ach_id = new_row[0] if new_row else None

                    if new_ach_id is not None:
                        conn.execute(
                            text(
                                "UPDATE guides "
                                "SET achievement_id = :new_id "
                                "WHERE achievement_summary_id = :old_id"
                            ),
                            {
                                "new_id": new_ach_id,
                                "old_id": old_summary_id,
                            },
                        )

                conn.commit()

        # ------------------------------------------------------------------
        # 3. Add missing columns to legacy users table.
        # ------------------------------------------------------------------
        if "users" in existing_tables:
            user_cols = {
                col["name"] for col in inspector.get_columns("users")
            }
            if "achievement_count" not in user_cols:
                conn.execute(
                    text(
                        "ALTER TABLE users "
                        "ADD COLUMN achievement_count INTEGER DEFAULT 0"
                    )
                )
                conn.commit()
