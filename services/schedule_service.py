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


from translations import WEEKDAY_NAMES, get_text


# ── Weekly schedule ───────────────────────────────────────────────────────────

def build_weekly_schedule(
    reference_date: date | None = None,
    lang: str = "en",
    club_id: str = "",
) -> str:
    if reference_date is None:
        reference_date = date.today()

    monday = reference_date - timedelta(days=reference_date.weekday())
    sunday = monday + timedelta(days=6)

    bookings = db.get_bookings_for_date_range(monday.isoformat(), sunday.isoformat(), club_id=club_id)

    by_date: dict[str, list[Booking]] = {}
    for b in bookings:
        by_date.setdefault(b.date, []).append(b)

    day_names = WEEKDAY_NAMES.get(lang, WEEKDAY_NAMES["en"])
    free_word  = get_text(lang, "free_label")

    lines = [f"📅  {monday.strftime('%d.%m')} — {sunday.strftime('%d.%m')}\n"]

    week_events = db.get_special_events_for_date_range(monday.isoformat(), sunday.isoformat(), club_id=club_id)
    ev_by_date: dict[str, list] = {}
    for ev in week_events:
        parts = ev["event_date"].replace(" ", "").split("–")
        if len(parts) == 2:
            try:
                from datetime import date as _d2
                s = _d2.fromisoformat(parts[0])
                e2 = _d2.fromisoformat(parts[1])
                cur = s
                while cur <= e2:
                    ev_by_date.setdefault(cur.isoformat(), []).append(ev)
                    cur = _d2.fromordinal(cur.toordinal() + 1)
            except Exception:
                pass
        else:
            ev_by_date.setdefault(ev["event_date"].strip(), []).append(ev)

    for d in _date_range(monday, sunday):
        day_str    = d.isoformat()
        day_name   = day_names[d.weekday()]
        date_str   = d.strftime("%d.%m")
        is_today   = d == date.today()
        today_mark = " ◀" if is_today else ""
        day_evs    = ev_by_date.get(day_str, [])
        has_event  = bool(day_evs)

        day_header = f"📆 {day_name}, {date_str}{today_mark}" + (" 🎉" if has_event else "")

        if day_str in by_date or has_event:
            lines.append(day_header)
            for b in by_date.get(day_str, []):
                lines.append(f"")
                lines.append(f"   🕐 {b.start_time} – {b.end_time}")
                lines.append(f"   📋 {b.title}")
                lines.append(f"   👤 {b.display_user}")
            for ev in day_evs:
                lines.append(f"")
                lines.append(f"   🎉 {ev['title']}")
                if ev.get("location"):
                    lines.append(f"   📍 {ev['location']}")
            lines.append("")
        else:
            free_slots = get_free_slots(d, club_id=club_id)
            lines.append(day_header)
            if free_slots:
                for s, e in free_slots:
                    lines.append(f"   🟢 {s} – {e}")
            else:
                lines.append(f"   {free_word}")
            lines.append("")

    return "\n".join(lines).strip()


# ── Monthly schedule ──────────────────────────────────────────────────────────

def build_monthly_schedule(year: int, month: int, lang: str = "en", club_id: str = "") -> str:
    from calendar import monthrange

    first = date(year, month, 1)
    last  = date(year, month, monthrange(year, month)[1])

    bookings = db.get_bookings_for_date_range(first.isoformat(), last.isoformat(), club_id=club_id)
    by_date: dict[str, list[Booking]] = {}
    for b in bookings:
        by_date.setdefault(b.date, []).append(b)

    from translations import MONTH_NAMES
    month_name = MONTH_NAMES.get(lang, MONTH_NAMES["en"])[month - 1]

    lines = [f"📅  {month_name} {year}\n"]

    month_events = db.get_special_events_for_date_range(first.isoformat(), last.isoformat(), club_id=club_id)
    mev_by_date: dict[str, list] = {}
    for ev in month_events:
        parts = ev["event_date"].replace(" ", "").split("–")
        if len(parts) == 2:
            try:
                from datetime import date as _d2
                s = _d2.fromisoformat(parts[0])
                e2 = _d2.fromisoformat(parts[1])
                cur = s
                while cur <= e2:
                    if cur.month == month:
                        mev_by_date.setdefault(cur.isoformat(), []).append(ev)
                    cur = _d2.fromordinal(cur.toordinal() + 1)
            except Exception:
                pass
        else:
            mev_by_date.setdefault(ev["event_date"].strip(), []).append(ev)

    for d in _date_range(first, last):
        day_str    = d.isoformat()
        is_today   = d == date.today()
        today_mark = " ◀" if is_today else ""
        day_evs    = mev_by_date.get(day_str, [])

        if day_str in by_date or day_evs:
            ev_mark = " 🎉" if day_evs else ""
            lines.append(f"📆 {d.day:02d}.{d.month:02d}{today_mark}{ev_mark}")
            for b in by_date.get(day_str, []):
                lines.append(f"")
                lines.append(f"   🕐 {b.start_time} – {b.end_time}")
                lines.append(f"   📋 {b.title}")
                lines.append(f"   👤 {b.display_user}")
            for ev in day_evs:
                lines.append(f"")
                lines.append(f"   🎉 {ev['title']}")
                if ev.get("location"):
                    lines.append(f"   📍 {ev['location']}")
            lines.append("")

    if len(lines) == 1:
        lines.append(get_text(lang, "no_bookings_this_month"))

    return "\n".join(lines).strip()


# ── Free slots ────────────────────────────────────────────────────────────────

def get_free_slots(target_date: date, club_id: str = "") -> list[tuple[str, str]]:
    bookings = db.get_bookings_for_date(target_date.isoformat(), club_id=club_id)
    bookings.sort(key=lambda b: b.start_time)

    free: list[tuple[str, str]] = []
    cursor = OFFICE_OPEN

    for b in bookings:
        book_start_h = int(b.start_time.split(":")[0])
        book_end_h   = int(b.end_time.split(":")[0])
        if cursor < book_start_h:
            free.append((f"{cursor:02d}:00", f"{book_start_h:02d}:00"))
        cursor = max(cursor, book_end_h)

    if cursor < OFFICE_CLOSE:
        free.append((f"{cursor:02d}:00", f"{OFFICE_CLOSE:02d}:00"))

    return free


def format_free_slots(target_date: date, club_id: str = "") -> str:
    slots = get_free_slots(target_date, club_id=club_id)
    header = f"🟢 {target_date.strftime('%d.%m')}:\n"
    if not slots:
        return header + "_No free time available._"
    body = "\n".join(f"  {s} – {e}" for s, e in slots)
    return header + body


def _date_in_event_range_str(date_str: str, event_date: str) -> bool:
    try:
        from datetime import date as _d
        parts = event_date.replace(" ", "").split("–")
        if len(parts) == 2:
            return _d.fromisoformat(parts[0]) <= _d.fromisoformat(date_str) <= _d.fromisoformat(parts[1])
        return date_str == event_date.strip()
    except Exception:
        return False
