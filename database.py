"""
database.py
Gestion de la base de données SQLite.
Toutes les opérations I/O passent par ce module.
"""

import sqlite3
import time
from contextlib import contextmanager

DB_PATH = "bot_data.db"


# ── Connexion ──────────────────────────────────────────────
@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Initialisation des tables ──────────────────────────────
def init_db():
    with get_db() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS economy (
            user_id     INTEGER PRIMARY KEY,
            coins       INTEGER DEFAULT 0,
            last_daily  REAL    DEFAULT 0,
            total_earned INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS warns (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            guild_id    INTEGER NOT NULL,
            reason      TEXT,
            moderator   INTEGER,
            timestamp   REAL DEFAULT (strftime('%s','now'))
        );

        CREATE TABLE IF NOT EXISTS quiz_scores (
            user_id     INTEGER PRIMARY KEY,
            correct     INTEGER DEFAULT 0,
            total       INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS inventory (
            user_id     INTEGER NOT NULL,
            item_id     TEXT    NOT NULL,
            bought_at   REAL    DEFAULT (strftime('%s','now')),
            PRIMARY KEY (user_id, item_id)
        );
        """)
    print("[DB] Base de données initialisée.")


# ══════════════════════════════════════════════
#  ÉCONOMIE
# ══════════════════════════════════════════════
def get_coins(user_id: int) -> int:
    with get_db() as db:
        row = db.execute("SELECT coins FROM economy WHERE user_id=?", (user_id,)).fetchone()
        return row["coins"] if row else 0


def add_coins(user_id: int, amount: int) -> int:
    with get_db() as db:
        db.execute("""
            INSERT INTO economy (user_id, coins, total_earned)
            VALUES (?, MAX(0,?), MAX(0,?))
            ON CONFLICT(user_id) DO UPDATE SET
                coins = MAX(0, coins + ?),
                total_earned = total_earned + MAX(0,?)
        """, (user_id, amount, amount, amount, amount))
        row = db.execute("SELECT coins FROM economy WHERE user_id=?", (user_id,)).fetchone()
        return row["coins"]


def set_coins(user_id: int, amount: int):
    with get_db() as db:
        db.execute("""
            INSERT INTO economy (user_id, coins) VALUES (?,?)
            ON CONFLICT(user_id) DO UPDATE SET coins=?
        """, (user_id, max(0, amount), max(0, amount)))


def get_last_daily(user_id: int) -> float:
    with get_db() as db:
        row = db.execute("SELECT last_daily FROM economy WHERE user_id=?", (user_id,)).fetchone()
        return row["last_daily"] if row else 0.0


def set_last_daily(user_id: int):
    with get_db() as db:
        db.execute("""
            INSERT INTO economy (user_id, last_daily) VALUES (?,?)
            ON CONFLICT(user_id) DO UPDATE SET last_daily=?
        """, (user_id, time.time(), time.time()))


def get_leaderboard(limit: int = 10):
    with get_db() as db:
        return db.execute(
            "SELECT user_id, coins FROM economy ORDER BY coins DESC LIMIT ?", (limit,)
        ).fetchall()


# ══════════════════════════════════════════════
#  WARNS
# ══════════════════════════════════════════════
def add_warn(user_id: int, guild_id: int, reason: str, moderator: int) -> int:
    with get_db() as db:
        db.execute(
            "INSERT INTO warns (user_id, guild_id, reason, moderator) VALUES (?,?,?,?)",
            (user_id, guild_id, reason, moderator)
        )
        count = db.execute(
            "SELECT COUNT(*) as c FROM warns WHERE user_id=? AND guild_id=?",
            (user_id, guild_id)
        ).fetchone()["c"]
        return count


def get_warns(user_id: int, guild_id: int):
    with get_db() as db:
        return db.execute(
            "SELECT * FROM warns WHERE user_id=? AND guild_id=? ORDER BY timestamp DESC",
            (user_id, guild_id)
        ).fetchall()


def clear_warns(user_id: int, guild_id: int):
    with get_db() as db:
        db.execute("DELETE FROM warns WHERE user_id=? AND guild_id=?", (user_id, guild_id))


# ══════════════════════════════════════════════
#  QUIZ
# ══════════════════════════════════════════════
def record_quiz_answer(user_id: int, correct: bool):
    with get_db() as db:
        db.execute("""
            INSERT INTO quiz_scores (user_id, correct, total) VALUES (?,?,1)
            ON CONFLICT(user_id) DO UPDATE SET
                correct = correct + ?,
                total   = total + 1
        """, (user_id, 1 if correct else 0, 1 if correct else 0))


def get_quiz_leaderboard(limit: int = 10):
    with get_db() as db:
        return db.execute(
            "SELECT user_id, correct, total FROM quiz_scores ORDER BY correct DESC LIMIT ?",
            (limit,)
        ).fetchall()


# ══════════════════════════════════════════════
#  INVENTAIRE
# ══════════════════════════════════════════════
def has_item(user_id: int, item_id: str) -> bool:
    with get_db() as db:
        row = db.execute(
            "SELECT 1 FROM inventory WHERE user_id=? AND item_id=?", (user_id, item_id)
        ).fetchone()
        return row is not None


def add_item(user_id: int, item_id: str):
    with get_db() as db:
        db.execute(
            "INSERT OR IGNORE INTO inventory (user_id, item_id) VALUES (?,?)",
            (user_id, item_id)
        )


def get_inventory(user_id: int):
    with get_db() as db:
        return [r["item_id"] for r in db.execute(
            "SELECT item_id FROM inventory WHERE user_id=?", (user_id,)
        ).fetchall()]
