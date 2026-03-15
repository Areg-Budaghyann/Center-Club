"""
services/schedule_service.py
-----------------------------
Logic for building human-readable schedules and computing free slots.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Iterator

import database as db
from config import OFFICE_OPEN, OFFICE_CLOSE
from models import Booking


# ── Helpers ───────────────────────────────────────────────────────────────────

def _date_range(start: date, end: date) -> Iterator[date]:
    """Yield every date from start to end inclusive."""
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


# ── Weekly schedule ───────────────────────────────────────────────────────────

def build_weekly_schedule(reference_date: date | None = None) -> str:
    """
    Return a formatted string of the week containing reference_date.
    Defaults to the current week (Monday–Sunday).
    """
    if reference_date is None:
        reference_date = date.today()

    monday = reference_date - timedelta(days=reference_date.weekday())
    sunday = monday + timedelta(days=6)

    bookings = db.get_bookings_for_date_range(monday.isoformat(), sunday.isoformat())

    # Group bookings by date
    by_date: dict[str, list[Booking]] = {}
    for b in bookings:
        by_date.setdefault(b.date, []).append(b)

    lines = [f"📅 *Schedule: {monday.strftime('%b %d')} – {sunday.strftime('%b %d')}*\n"]
    for d in _date_range(monday, sunday):
        day_str = d.isoformat()
        day_label = f"*{DAY_NAMES[d.weekday()]}* ({d.strftime('%b %d')})"
        if day_str in by_date:
            lines.append(day_label)
            for b in by_date[day_str]:
                lines.append(f"  {b.short_label()}")
        else:
            lines.append(f"{day_label}\n  _Free_")
        lines.append("")  # blank line between days

    return "\n".join(lines).strip()


# ── Monthly schedule ──────────────────────────────────────────────────────────

def build_monthly_schedule(year: int, month: int) -> str:
    """Return a compact monthly schedule string."""
    from calendar import monthrange

    first = date(year, month, 1)
    last  = date(year, month, monthrange(year, month)[1])

    bookings = db.get_bookings_for_date_range(first.isoformat(), last.isoformat())
    by_date: dict[str, list[Booking]] = {}
    for b in bookings:
        by_date.setdefault(b.date, []).append(b)

    month_name = first.strftime("%B %Y")
    lines = [f"📅 *{month_name}*\n"]
    for d in _date_range(first, last):
        day_str = d.isoformat()
        if day_str in by_date:
            day_label = f"*{d.strftime('%d %a')}*"
            lines.append(day_label)
            for b in by_date[day_str]:
                lines.append(f"  {b.short_label()}")
            lines.append("")

    if len(lines) == 2:
        lines.append("_No bookings this month._")

    return "\n".join(lines).strip()


# ── Free slots ────────────────────────────────────────────────────────────────

def get_free_slots(target_date: date) -> list[tuple[str, str]]:
    """
    Return a list of (start_str, end_str) free time windows on target_date,
    clipped to OFFICE_OPEN – OFFICE_CLOSE.
    """
    bookings = db.get_bookings_for_date(target_date.isoformat())
    # Sort by start time
    bookings.sort(key=lambda b: b.start_time)

    free: list[tuple[str, str]] = []
    cursor = OFFICE_OPEN  # current hour pointer

    for b in bookings:
        book_start_h = int(b.start_time.split(":")[0])
        book_end_h   = int(b.end_time.split(":")[0])
        if cursor < book_start_h:
            free.append((f"{cursor:02d}:00", f"{book_start_h:02d}:00"))
        cursor = max(cursor, book_end_h)

    if cursor < OFFICE_CLOSE:
        free.append((f"{cursor:02d}:00", f"{OFFICE_CLOSE:02d}:00"))

    return free


def format_free_slots(target_date: date) -> str:
    slots = get_free_slots(target_date)
    header = f"🟢 *Free slots on {target_date.strftime('%A, %b %d')}:*\n"
    if not slots:
        return header + "_No free time available._"
    body = "\n".join(f"  {s} – {e}" for s, e in slots)
    return header + body
