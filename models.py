"""
models.py
---------
Pure-Python data model for a booking.
No database logic here — just structure and helpers.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta


@dataclass
class Booking:
    id: int
    user_id: int
    username: str
    title: str
    date: str          # "YYYY-MM-DD"
    start_time: str    # "HH:MM"
    duration: float    # decimal hours, e.g. 1.5 = 90 minutes
    created_at: str    # ISO datetime string
    club_id: str = ""  # club this booking belongs to

    # ── derived helpers ────────────────────────────────────────────────────

    @property
    def start_dt(self) -> datetime:
        return datetime.fromisoformat(f"{self.date}T{self.start_time}")

    @property
    def end_dt(self) -> datetime:
        return self.start_dt + timedelta(hours=self.duration)

    @property
    def end_time(self) -> str:
        return self.end_dt.strftime("%H:%M")

    def overlaps(self, other: "Booking") -> bool:
        return self.start_dt < other.end_dt and other.start_dt < self.end_dt

    @property
    def display_user(self) -> str:
        if self.username and " " not in self.username:
            return f"@{self.username}"
        return self.username or "Unknown"

    @property
    def duration_display(self) -> str:
        total_mins = round(self.duration * 60)
        h, m = divmod(total_mins, 60)
        if m == 0:
            return f"{h}h"
        return f"{h}h {m}m"

    def short_label(self) -> str:
        return f"{self.start_time} – {self.end_time} | {self.title} | {self.display_user}"

    def full_text(self) -> str:
        return (
            f"📋 {self.title}\n"
            f"📅 {self.date}\n"
            f"🕐 {self.start_time} – {self.end_time} ({self.duration_display})\n"
            f"👤 {self.display_user}"
        )
