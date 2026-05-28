"""
services/booking_service.py
----------------------------
Business logic for creating, cancelling, and editing bookings.
Conflict detection lives here.
"""

from __future__ import annotations

import logging
from typing import Optional

import database as db
from models import Booking

logger = logging.getLogger(__name__)


# ── Conflict detection ────────────────────────────────────────────────────────

def find_conflict(
    date: str,
    start_time: str,
    duration: float,
    club_id: str = "",
    exclude_id: Optional[int] = None,
) -> Optional[Booking]:
    """
    Return the first booking that overlaps with the proposed slot,
    or None if the slot is free.

    exclude_id: skip this booking id (used when editing an existing booking).
    """
    candidate = Booking(
        id=0,
        user_id=0,
        username="",
        title="",
        date=date,
        start_time=start_time,
        duration=duration,
        created_at="",
    )
    existing = db.get_bookings_for_date(date, club_id=club_id)
    for b in existing:
        if b.id == exclude_id:
            continue
        if candidate.overlaps(b):
            return b
    return None


# ── Create ────────────────────────────────────────────────────────────────────

def create_booking(
    user_id: int,
    username: str,
    title: str,
    date: str,
    start_time: str,
    duration: float,
    club_id: str = "",
) -> tuple[Booking | None, Booking | None]:
    """
    Try to create a booking.
    Returns (new_booking, None) on success.
    Returns (None, conflicting_booking) on conflict.
    """
    conflict = find_conflict(date, start_time, duration, club_id=club_id)
    if conflict:
        logger.info("Booking rejected — conflict with id=%d", conflict.id)
        return None, conflict

    new_booking = db.create_booking(user_id, username, title, date, start_time, duration, club_id=club_id)
    logger.info("Booking created id=%d by user_id=%d", new_booking.id, user_id)
    return new_booking, None


# ── Cancel ────────────────────────────────────────────────────────────────────

def cancel_booking(booking_id: int, requesting_user_id: int) -> tuple[bool, str]:
    """
    Cancel a booking.
    Returns (True, "") on success.
    Returns (False, reason) if the booking doesn't exist or the user doesn't own it.
    """
    booking = db.get_booking_by_id(booking_id)
    if not booking:
        return False, "Booking not found."
    if booking.user_id != requesting_user_id:
        return False, "You can only cancel your own bookings."
    db.delete_booking(booking_id)
    return True, ""


# ── Edit ──────────────────────────────────────────────────────────────────────

def edit_booking(
    booking_id: int,
    requesting_user_id: int,
    **fields,
) -> tuple[Booking | None, str]:
    """
    Edit a booking's fields.
    Returns (updated_booking, "") on success.
    Returns (None, reason) on failure.
    """
    booking = db.get_booking_by_id(booking_id)
    if not booking:
        return None, "Booking not found."
    if booking.user_id != requesting_user_id:
        return None, "You can only edit your own bookings."

    new_date       = fields.get("date",       booking.date)
    new_start_time = fields.get("start_time", booking.start_time)
    new_duration   = fields.get("duration",   booking.duration)

    conflict = find_conflict(
        new_date, new_start_time, new_duration,
        club_id=booking.club_id,
        exclude_id=booking_id,
    )
    if conflict:
        return None, (
            f"Time conflict with an existing booking:\n"
            f"{conflict.start_time} – {conflict.end_time} | {conflict.title} (@{conflict.username})"
        )

    updated = db.update_booking(booking_id, **fields)
    return updated, ""
