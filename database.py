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
    """Open a connection with row_factory and WAL mode enabled."""
    conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


# ── Schema initialisation ─────────────────────────────────────────────────────

def init_db() -> None:
    """Create tables and indexes if they don't exist yet. Call once at startup."""
    with _connect() as conn:
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
