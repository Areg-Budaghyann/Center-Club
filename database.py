"""
database.py
-----------
All database access is centralised here.
Handlers and services NEVER write SQL themselves — they call functions
defined in this module.

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
    """Open a connection with row_factory. WAL is set once in init_db."""
    conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


# ── Schema initialisation ─────────────────────────────────────────────────────

def init_db() -> None:
    import os
    db_dir = os.path.dirname(DATABASE_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    """Create tables and indexes if they don't exist yet. Call once at startup."""
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
                duration    INTEGER NOT NULL,
                created_at  TEXT    NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_bookings_date ON bookings(date);
            CREATE INDEX IF NOT EXISTS idx_bookings_user ON bookings(user_id);

            CREATE TABLE IF NOT EXISTS reminder_sent (
                booking_id  INTEGER PRIMARY KEY,
                sent_at     TEXT NOT NULL
            );

            -- Tracks every user who has ever used the bot so we can broadcast notifications
            CREATE TABLE IF NOT EXISTS users (
                user_id     INTEGER PRIMARY KEY,
                username    TEXT    NOT NULL,
                lang        TEXT    NOT NULL DEFAULT 'en',
                first_seen  TEXT    NOT NULL
            );
        """)
    logger.info("Database initialised at %s", DATABASE_PATH)


# ── Row → model conversion ────────────────────────────────────────────────────

def _row_to_booking(row: sqlite3.Row) -> Booking:
    return Booking(
        id         = row["id"],
        user_id    = row["user_id"],
        username   = row["username"],
        title      = row["title"],
        date       = row["date"],
        start_time = row["start_time"],
        duration   = row["duration"],
        created_at = row["created_at"],
    )


# ── Write operations ──────────────────────────────────────────────────────────

def create_booking(
    user_id: int,
    username: str,
    title: str,
    date: str,
    start_time: str,
    duration: int,
) -> Booking:
    """Insert a new booking and return the created Booking object."""
    created_at = datetime.utcnow().isoformat(timespec="seconds")
    with _connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO bookings (user_id, username, title, date, start_time, duration, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, username, title, date, start_time, duration, created_at),
        )
        booking_id = cursor.lastrowid
    return get_booking_by_id(booking_id)


def delete_booking(booking_id: int) -> bool:
    """Delete a booking by id. Returns True if a row was deleted."""
    with _connect() as conn:
        cursor = conn.execute("DELETE FROM bookings WHERE id = ?", (booking_id,))
    return cursor.rowcount > 0


def update_booking(booking_id: int, **fields) -> Optional[Booking]:
    """
    Update arbitrary fields of a booking.
    Allowed fields: title, date, start_time, duration.
    Returns the updated Booking or None if not found.
    """
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


def get_bookings_for_date(date: str) -> list[Booking]:
    """Return all bookings on a given date, sorted by start_time."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM bookings WHERE date = ? ORDER BY start_time",
            (date,),
        ).fetchall()
    return [_row_to_booking(r) for r in rows]


def get_bookings_for_date_range(start_date: str, end_date: str) -> list[Booking]:
    """Return all bookings between start_date and end_date (inclusive)."""
    with _connect() as conn:
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
    """Return all future (and today's) bookings for a user, sorted by date/time."""
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
    """
    Return bookings whose datetime falls in [window_start, window_end]
    and that have NOT yet had a reminder sent.
    window_start / window_end are ISO datetime strings 'YYYY-MM-DDTHH:MM'.
    """
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
    weekday: int,          # 0=Mon, 1=Tue, 2=Wed, 3=Thu, 4=Fri, 5=Sat, 6=Sun
    start_time: str,       # "HH:MM"
    duration: int,         # hours (can be fractional via end_time override)
    end_time: str,         # "HH:MM" — used for display; duration is stored as ceil
    from_date: str,        # ISO "YYYY-MM-DD" inclusive
    to_date: str,          # ISO "YYYY-MM-DD" inclusive
) -> tuple[list[Booking], list[str]]:
    """
    Create a booking on every occurrence of `weekday` between from_date and to_date.
    Skips any date that already has a conflicting booking.

    Returns:
        (created, skipped_dates) where skipped_dates are ISO strings that had conflicts.
    """
    from datetime import date, timedelta

    created: list[Booking] = []
    skipped: list[str] = []

    start = date.fromisoformat(from_date)
    end   = date.fromisoformat(to_date)

    # Advance to the first occurrence of the target weekday
    days_ahead = (weekday - start.weekday()) % 7
    current = start + timedelta(days=days_ahead)

    while current <= end:
        date_str = current.isoformat()

        # Conflict check
        conflict = False
        req_start = int(start_time.split(":")[0])
        req_end   = req_start + duration
        for b in get_bookings_for_date(date_str):
            ex_start = int(b.start_time.split(":")[0])
            ex_end   = int(b.end_time.split(":")[0])
            if req_start < ex_end and req_end > ex_start:
                conflict = True
                break

        if conflict:
            skipped.append(date_str)
        else:
            b = create_booking(user_id, username, title, date_str, start_time, duration)
            created.append(b)

        current += timedelta(weeks=1)

    return created, skipped


# ── User registry ─────────────────────────────────────────────────────────────

def upsert_user(user_id: int, username: str, lang: str = "en") -> None:
    """Register or update a user. Called on every interaction."""
    from datetime import datetime
    first_seen = datetime.utcnow().isoformat(timespec="seconds")
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO users (user_id, username, lang, first_seen)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET username=excluded.username, lang=excluded.lang
            """,
            (user_id, username, lang, first_seen),
        )


def get_user_lang(user_id: int):
    """Return stored lang for user, or None if user not in DB."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT lang FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()
    return row["lang"] if row else None


# ── Special events ────────────────────────────────────────────────────────────

def create_special_event(title: str, event_date: str, event_time: str, location: str) -> int:
    """Insert a new special event, return its id."""
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO special_events (title, event_date, event_time, location) VALUES (?,?,?,?)",
            (title, event_date, event_time, location),
        )
        return cur.lastrowid


def get_all_special_events() -> list[dict]:
    """Return all upcoming special events sorted by date."""
    from datetime import date
    today = date.today().isoformat()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM special_events WHERE event_date >= ? ORDER BY event_date, event_time",
            (today,),
        ).fetchall()
    return [dict(r) for r in rows]


def delete_special_event(event_id: int) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM special_events WHERE id = ?", (event_id,))


def get_all_user_ids() -> list[int]:
    """Return all known user IDs for broadcast notifications."""
    with _connect() as conn:
        rows = conn.execute("SELECT user_id FROM users").fetchall()
    return [r["user_id"] for r in rows]
