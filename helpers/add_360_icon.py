#!/usr/bin/env python3

import sqlite3
import sys

DATABASE = "../overachiever.db"


def add_icon(db_path: str, achievement_id: int, title_id: int, url: str):
    db = sqlite3.connect(db_path)
    cursor = db.cursor()
    cursor.execute(
        "SELECT * FROM icon360 WHERE achievement_id = ? AND title_id = ?",
        (achievement_id, title_id),
    )
    if cursor.fetchone():
        print(
            f"Icon for achievement {achievement_id} and title {title_id} already exists"
        )
        db.close()
        return
    cursor.execute(
        "INSERT INTO icon360 (achievement_id, title_id, url) VALUES (?, ?, ?)",
        (achievement_id, title_id, url),
    )
    db.commit()
    db.close()


if __name__ == "__main__":
    if len(sys.argv) != 5:
        print(f"Usage: {sys.argv[0]} <db_path> <achievement_id> <title_id> <url>")
        sys.exit(1)

    db_path = sys.argv[1]
    achievement_id = int(sys.argv[2])
    title_id = int(sys.argv[3])
    url = sys.argv[4]
    add_icon(db_path, achievement_id, title_id, url)
