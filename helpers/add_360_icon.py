#!/usr/bin/env python3

import argparse
import sqlite3

DATABASE = "../overachiever.db"


def add_icon(db_path: str, achievement_id: int, title_id: int, url: str):
    db = sqlite3.connect(db_path)
    cursor = db.cursor()
    cursor.execute(
        "INSERT INTO icon360 (achievement_id, title_id, url) VALUES (?, ?, ?)",
        (achievement_id, title_id, url),
    )
    db.commit()
    db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Add a 360 icon to the database")
    parser.add_argument("db_path", help="Path to the database file")
    parser.add_argument("achievement_id", type=int, help="Achievement ID")
    parser.add_argument("title_id", type=int, help="Title ID")
    parser.add_argument("url", help="Icon URL")
    args = parser.parse_args()
    add_icon(args.db_path, args.achievement_id, args.title_id, args.url)
