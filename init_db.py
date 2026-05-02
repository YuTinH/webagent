import sqlite3
import time
from pathlib import Path

from runtime_paths import database_dir, db_path
ROOT = Path(__file__).resolve().parent
DB_PATH = db_path()
SCHEMA_PATH = database_dir() / "schema.sql"
SEED_PATH = database_dir() / "seed_data.sql"


def _exec_script(cur: sqlite3.Cursor, path: Path) -> None:
    cur.executescript(path.read_text(encoding="utf-8"))


def _remove_db_files() -> None:
    for suffix in ("", "-wal", "-shm"):
        path = Path(f"{DB_PATH}{suffix}")
        try:
            if path.exists():
                path.unlink()
        except FileNotFoundError:
            pass


def _looks_like_sqlite_db(path: Path) -> bool:
    if not path.exists():
        return True
    try:
        with path.open("rb") as fh:
            header = fh.read(16)
        return header == b"SQLite format 3\x00"
    except Exception:
        return False


def _drop_all_objects(cur: sqlite3.Cursor) -> None:
    cur.execute("PRAGMA foreign_keys=OFF")
    rows = cur.execute(
        """
        SELECT type, name
        FROM sqlite_master
        WHERE name NOT LIKE 'sqlite_%'
        ORDER BY
          CASE type
            WHEN 'trigger' THEN 0
            WHEN 'index' THEN 1
            WHEN 'table' THEN 2
            ELSE 3
          END,
          name
        """
    ).fetchall()
    for obj_type, name in rows:
        if obj_type == "table":
            cur.execute(f'DROP TABLE IF EXISTS "{name}"')
        elif obj_type == "index":
            cur.execute(f'DROP INDEX IF EXISTS "{name}"')
        elif obj_type == "trigger":
            cur.execute(f'DROP TRIGGER IF EXISTS "{name}"')


def init_db() -> None:
    max_retries = 10
    for attempt in range(max_retries):
        conn = None
        try:
            if not _looks_like_sqlite_db(Path(DB_PATH)):
                _remove_db_files()
            conn = sqlite3.connect(DB_PATH, timeout=30)
            cur = conn.cursor()
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA synchronous=NORMAL")
            _drop_all_objects(cur)

            _exec_script(cur, SCHEMA_PATH)
            _exec_script(cur, SEED_PATH)

            cur.execute("PRAGMA foreign_keys=ON")
            conn.commit()
            conn.close()
            print("Database initialized from schema + seed data.")
            return
        except sqlite3.OperationalError as exc:
            if conn is not None:
                conn.close()
            if "locked" in str(exc).lower() and attempt < max_retries - 1:
                time.sleep(1)
                continue
            raise
        except sqlite3.DatabaseError as exc:
            if conn is not None:
                conn.close()
            if any(token in str(exc).lower() for token in ("malformed", "not a database")) and attempt < max_retries - 1:
                _remove_db_files()
                time.sleep(0.2)
                continue
            raise

    raise RuntimeError("DB lock timeout during init_db")


if __name__ == "__main__":
    init_db()
