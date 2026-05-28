"""
database.py
-----------
All database access is centralised here.
Uses SQLite with WAL journal mode for safe concurrent reads.
"""

import sqlite3
import logging
from datetime import datetime
from typing import Optional

from config import DATABASE_PATH
from models import Booking

logger = logging.getLogger(__name__)


# ── Connection factory ────────────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


# ── Schema initialisation ─────────────────────────────────────────────────────

def _run_migrations() -> None:
    """Safe schema migrations — add new columns/tables to existing DBs."""
    with _connect() as conn:
        # pending_notifications table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS pending_notifications (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                chat_id     INTEGER NOT NULL,
                message_id  INTEGER NOT NULL,
                sent_at     TEXT DEFAULT (datetime('now'))
            )
        """)
        # event_reminder_sent table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS event_reminder_sent (
                event_id    INTEGER PRIMARY KEY,
                sent_at     TEXT NOT NULL
            )
        """)
        # special_events table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS special_events (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                title       TEXT    NOT NULL,
                event_date  TEXT    NOT NULL,
                event_time  TEXT    NOT NULL,
                location    TEXT    NOT NULL,
                description TEXT    DEFAULT '',
                created_at  TEXT    DEFAULT (datetime('now'))
            )
        """)
        # Add new columns — all wrapped in try/except for idempotency
        for stmt in [
            "ALTER TABLE special_events ADD COLUMN description TEXT DEFAULT ''",
            "ALTER TABLE special_events ADD COLUMN club_id TEXT DEFAULT ''",
            "ALTER TABLE special_events ADD COLUMN created_by INTEGER DEFAULT 0",
            "ALTER TABLE bookings ADD COLUMN club_id TEXT DEFAULT ''",
            "ALTER TABLE users ADD COLUMN club_id TEXT DEFAULT ''",
        ]:
            try:
                conn.execute(stmt)
            except Exception:
                pass
        # Index on club_id for bookings (after column exists)
        try:
            conn.execute("CREATE INDEX IF NOT EXISTS idx_bookings_club ON bookings(club_id)")
        except Exception:
            pass


def init_db() -> None:
    import os
    db_dir = os.path.dirname(DATABASE_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

    with _connect() as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS bookings (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                username    TEXT    NOT NULL,
                title       TEXT    NOT NULL,
                date        TEXT    NOT NULL,
                start_time  TEXT    NOT NULL,
                duration    REAL    NOT NULL,
                created_at  TEXT    NOT NULL,
                club_id     TEXT    DEFAULT ''
            );

            CREATE INDEX IF NOT EXISTS idx_bookings_date ON bookings(date);
            CREATE INDEX IF NOT EXISTS idx_bookings_user ON bookings(user_id);

            CREATE TABLE IF NOT EXISTS reminder_sent (
                booking_id  INTEGER PRIMARY KEY,
                sent_at     TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS users (
                user_id     INTEGER PRIMARY KEY,
                username    TEXT    NOT NULL,
                lang        TEXT    NOT NULL DEFAULT 'en',
                club_id     TEXT    NOT NULL DEFAULT '',
                first_seen  TEXT    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS pending_notifications (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                chat_id     INTEGER NOT NULL,
                message_id  INTEGER NOT NULL,
                sent_at     TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS event_reminder_sent (
                event_id    INTEGER PRIMARY KEY,
                sent_at     TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS special_events (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                title       TEXT    NOT NULL,
                event_date  TEXT    NOT NULL,
                event_time  TEXT    NOT NULL DEFAULT '',
                location    TEXT    NOT NULL DEFAULT '',
                description TEXT    DEFAULT '',
                club_id     TEXT    DEFAULT '',
                created_by  INTEGER DEFAULT 0,
                created_at  TEXT    DEFAULT (datetime('now'))
            );
        """)

    # Run migrations for existing DBs (adds missing columns)
    _run_migrations()
    logger.info("Database initialised at %s", DATABASE_PATH)


# ── Row → model conversion ────────────────────────────────────────────────────

def _row_to_booking(row: sqlite3.Row) -> Booking:
    club_id = ""
    try:
        club_id = row["club_id"] or ""
    except (IndexError, KeyError):
        pass
    return Booking(
        id         = row["id"],
        user_id    = row["user_id"],
        username   = row["username"],
        title      = row["title"],
        date       = row["date"],
        start_time = row["start_time"],
        duration   = float(row["duration"]),
        created_at = row["created_at"],
        club_id    = club_id,
    )


# ── Write operations ──────────────────────────────────────────────────────────

def create_booking(
    user_id: int,
    username: str,
    title: str,
    date: str,
    start_time: str,
    duration: float,
    club_id: str = "",
) -> Booking:
    created_at = datetime.utcnow().isoformat(timespec="seconds")
    with _connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO bookings (user_id, username, title, date, start_time, duration, created_at, club_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, username, title, date, start_time, duration, created_at, club_id),
        )
        booking_id = cursor.lastrowid
    return get_booking_by_id(booking_id)


def delete_booking(booking_id: int) -> bool:
    with _connect() as conn:
        cursor = conn.execute("DELETE FROM bookings WHERE id = ?", (booking_id,))
    return cursor.rowcount > 0


def update_booking(booking_id: int, **fields) -> Optional[Booking]:
    allowed = {"title", "date", "start_time", "duration"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return get_booking_by_id(booking_id)
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [booking_id]
    with _connect() as conn:
        conn.execute(f"UPDATE bookings SET {set_clause} WHERE id = ?", values)
    return get_booking_by_id(booking_id)


# ── Read operations ───────────────────────────────────────────────────────────

def get_booking_by_id(booking_id: int) -> Optional[Booking]:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM bookings WHERE id = ?", (booking_id,)
        ).fetchone()
    return _row_to_booking(row) if row else None


def get_bookings_for_date(date: str, club_id: str = "") -> list[Booking]:
    with _connect() as conn:
        if club_id:
            rows = conn.execute(
                "SELECT * FROM bookings WHERE date = ? AND club_id = ? ORDER BY start_time",
                (date, club_id),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM bookings WHERE date = ? ORDER BY start_time",
                (date,),
            ).fetchall()
    return [_row_to_booking(r) for r in rows]


def get_bookings_for_date_range(start_date: str, end_date: str, club_id: str = "") -> list[Booking]:
    with _connect() as conn:
        if club_id:
            rows = conn.execute(
                """
                SELECT * FROM bookings
                WHERE date >= ? AND date <= ? AND club_id = ?
                ORDER BY date, start_time
                """,
                (start_date, end_date, club_id),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT * FROM bookings
                WHERE date >= ? AND date <= ?
                ORDER BY date, start_time
                """,
                (start_date, end_date),
            ).fetchall()
    return [_row_to_booking(r) for r in rows]


def get_user_bookings(user_id: int) -> list[Booking]:
    today = datetime.utcnow().date().isoformat()
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM bookings
            WHERE user_id = ? AND date >= ?
            ORDER BY date, start_time
            """,
            (user_id, today),
        ).fetchall()
    return [_row_to_booking(r) for r in rows]


def get_upcoming_bookings_needing_reminder(window_start: str, window_end: str) -> list[Booking]:
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT b.*
            FROM bookings b
            LEFT JOIN reminder_sent rs ON rs.booking_id = b.id
            WHERE rs.booking_id IS NULL
              AND (b.date || 'T' || b.start_time) >= ?
              AND (b.date || 'T' || b.start_time) <= ?
            """,
            (window_start, window_end),
        ).fetchall()
    return [_row_to_booking(r) for r in rows]


def mark_reminder_sent(booking_id: int) -> None:
    sent_at = datetime.utcnow().isoformat(timespec="seconds")
    with _connect() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO reminder_sent (booking_id, sent_at) VALUES (?, ?)",
            (booking_id, sent_at),
        )


# ── Bulk / recurring operations ───────────────────────────────────────────────

def create_recurring_bookings(
    user_id: int,
    username: str,
    title: str,
    weekday: int,
    start_time: str,
    duration: float,
    end_time: str,
    from_date: str,
    to_date: str,
    club_id: str = "",
) -> tuple[list[Booking], list[str]]:
    from datetime import date, timedelta

    created: list[Booking] = []
    skipped: list[str] = []

    start = date.fromisoformat(from_date)
    end   = date.fromisoformat(to_date)

    days_ahead = (weekday - start.weekday()) % 7
    current = start + timedelta(days=days_ahead)

    while current <= end:
        date_str = current.isoformat()

        conflict = False
        from models import Booking as _B
        from datetime import datetime as _dt
        candidate = _B(id=0, user_id=0, username="", title="",
                       date=date_str, start_time=start_time, duration=duration, created_at="")
        for b in get_bookings_for_date(date_str, club_id):
            if candidate.overlaps(b):
                conflict = True
                break

        if conflict:
            skipped.append(date_str)
        else:
            b = create_booking(user_id, username, title, date_str, start_time, duration, club_id)
            created.append(b)

        current += timedelta(weeks=1)

    return created, skipped


# ── User registry ─────────────────────────────────────────────────────────────

def upsert_user(user_id: int, username: str, lang: str = "en", club_id: str = "") -> None:
    first_seen = datetime.utcnow().isoformat(timespec="seconds")
    with _connect() as conn:
        if club_id:
            conn.execute(
                """
                INSERT INTO users (user_id, username, lang, club_id, first_seen)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    username=excluded.username,
                    lang=excluded.lang,
                    club_id=excluded.club_id
                """,
                (user_id, username, lang, club_id, first_seen),
            )
        else:
            conn.execute(
                """
                INSERT INTO users (user_id, username, lang, first_seen)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    username=excluded.username,
                    lang=excluded.lang
                """,
                (user_id, username, lang, first_seen),
            )


def get_user_lang(user_id: int):
    with _connect() as conn:
        row = conn.execute(
            "SELECT lang FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()
    return row["lang"] if row else None


def get_user_club(user_id: int) -> Optional[str]:
    """Return stored club_id for user, or None if not found."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT club_id FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()
    if row and row["club_id"]:
        return row["club_id"]
    return None


def get_all_user_ids() -> list[int]:
    with _connect() as conn:
        rows = conn.execute("SELECT user_id FROM users").fetchall()
    return [r["user_id"] for r in rows]


def get_all_user_ids_for_club(club_id: str) -> list[int]:
    """Return all user IDs belonging to a specific club."""
    if not club_id:
        return get_all_user_ids()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT user_id FROM users WHERE club_id = ?", (club_id,)
        ).fetchall()
    return [r["user_id"] for r in rows]


# ── Notifications tracking ────────────────────────────────────────────────────

def save_notification(user_id: int, chat_id: int, message_id: int) -> None:
    try:
        with _connect() as conn:
            conn.execute(
                "INSERT INTO pending_notifications (user_id, chat_id, message_id) VALUES (?,?,?)",
                (user_id, chat_id, message_id)
            )
    except Exception:
        pass


def get_all_notifications() -> list[dict]:
    try:
        with _connect() as conn:
            rows = conn.execute(
                "SELECT * FROM pending_notifications ORDER BY sent_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []


def clear_notifications(user_id: int = None) -> int:
    try:
        with _connect() as conn:
            if user_id:
                cur = conn.execute(
                    "DELETE FROM pending_notifications WHERE user_id = ?", (user_id,)
                )
            else:
                cur = conn.execute("DELETE FROM pending_notifications")
        return cur.rowcount
    except Exception:
        return 0


# ── Special events ────────────────────────────────────────────────────────────

def _ensure_special_events_table() -> None:
    """Idempotent migration: ensure special_events has all needed columns."""
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS special_events (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                title       TEXT    NOT NULL,
                event_date  TEXT    NOT NULL,
                event_time  TEXT    NOT NULL DEFAULT '',
                location    TEXT    NOT NULL DEFAULT '',
                description TEXT    DEFAULT '',
                club_id     TEXT    DEFAULT '',
                created_by  INTEGER DEFAULT 0,
                created_at  TEXT    DEFAULT (datetime('now'))
            )
        """)
        for stmt in [
            "ALTER TABLE special_events ADD COLUMN description TEXT DEFAULT ''",
            "ALTER TABLE special_events ADD COLUMN club_id TEXT DEFAULT ''",
            "ALTER TABLE special_events ADD COLUMN created_by INTEGER DEFAULT 0",
        ]:
            try:
                conn.execute(stmt)
            except Exception:
                pass


def create_special_event(
    title: str,
    event_date: str,
    event_time: str,
    location: str,
    description: str = "",
    club_id: str = "",
    created_by: int = 0,
) -> int:
    _ensure_special_events_table()
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO special_events
               (title, event_date, event_time, location, description, club_id, created_by)
               VALUES (?,?,?,?,?,?,?)""",
            (title, event_date, event_time, location, description, club_id, created_by),
        )
        return cur.lastrowid


def get_special_events_for_date_range(
    start_date: str, end_date: str, club_id: str = ""
) -> list[dict]:
    _ensure_special_events_table()
    with _connect() as conn:
        if club_id:
            rows = conn.execute(
                """SELECT * FROM special_events
                   WHERE event_date >= ? AND event_date <= ? AND club_id = ?
                   ORDER BY event_date""",
                (start_date, end_date, club_id),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT * FROM special_events
                   WHERE event_date >= ? AND event_date <= ?
                   ORDER BY event_date""",
                (start_date, end_date),
            ).fetchall()
    return [dict(r) for r in rows]


def get_special_events_for_month(year: int, month: int, club_id: str = "") -> list[dict]:
    _ensure_special_events_table()
    from datetime import date
    from calendar import monthrange
    first = date(year, month, 1).isoformat()
    last  = date(year, month, monthrange(year, month)[1]).isoformat()
    return get_special_events_for_date_range(first, last, club_id)


def get_all_special_events(club_id: str = "") -> list[dict]:
    _ensure_special_events_table()
    from datetime import date
    today = date.today().isoformat()
    with _connect() as conn:
        if club_id:
            rows = conn.execute(
                """SELECT * FROM special_events
                   WHERE event_date >= ? AND club_id = ?
                   ORDER BY event_date, event_time""",
                (today, club_id),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT * FROM special_events
                   WHERE event_date >= ?
                   ORDER BY event_date, event_time""",
                (today,),
            ).fetchall()
    return [dict(r) for r in rows]


def delete_special_event(event_id: int) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM special_events WHERE id = ?", (event_id,))
