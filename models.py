"""
models.py
---------
Pure-Python data model for a booking.
No database logic here — just structure and helpers.
"""

from dataclasses import dataclass
from datetime import datetime, time, timedelta


@dataclass
class Booking:
    id: int
    user_id: int
    username: str
    title: str
    date: str          # "YYYY-MM-DD"
    start_time: str    # "HH:MM"
    duration: int      # hours
    created_at: str    # ISO datetime string

    # ── derived helpers ────────────────────────────────────────────────────

    @property
    def start_dt(self) -> datetime:
        """Start as a datetime object."""
        return datetime.fromisoformat(f"{self.date}T{self.start_time}")

    @property
    def end_dt(self) -> datetime:
        """End as a datetime object."""
        return self.start_dt + timedelta(hours=self.duration)

    @property
    def end_time(self) -> str:
        """End time as 'HH:MM' string."""
        return self.end_dt.strftime("%H:%M")

    def overlaps(self, other: "Booking") -> bool:
        """Return True if this booking overlaps with *other* (same date assumed)."""
        return self.start_dt < other.end_dt and other.start_dt < self.end_dt

    def short_label(self) -> str:
        """One-line summary used in schedule views."""
        return f"{self.start_time} – {self.end_time} | {self.title} | @{self.username}"

    def full_text(self) -> str:
        """Multi-line detail card."""
        return (
            f"📋 *{self.title}*\n"
            f"📅 {self.date}\n"
            f"🕐 {self.start_time} – {self.end_time} ({self.duration}h)\n"
            f"👤 @{self.username}"
        )
