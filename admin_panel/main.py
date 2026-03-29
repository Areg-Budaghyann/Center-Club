"""
admin_panel/main.py
--------------------
FastAPI admin panel for Center Club Telegram Bot.
Reads from the same SQLite database as the bot.
"""

import os
import sqlite3
import secrets
from datetime import datetime, date
from typing import Optional, List
from pathlib import Path

from fastapi import FastAPI, Request, HTTPException, Depends, Form, status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBasic, HTTPBasicCredentials

# ── Config ────────────────────────────────────────────────────────────────────

# Smart DB path detection
_default_db = "/data/office.db"
if not os.path.exists(_default_db):
    # Try common local paths
    _candidates = [
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "office_test.db"),
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "office.db"),
        "office_test.db",
        "office.db",
    ]
    for _c in _candidates:
        if os.path.exists(_c):
            _default_db = _c
            break

DB_PATH = os.getenv("DATABASE_PATH", _default_db)
BOT_TOKEN    = os.getenv("BOT_TOKEN", "")
ADMIN_USER   = os.getenv("PANEL_USER",    "admin")
ADMIN_PASS   = os.getenv("PANEL_PASS",    "changeme")
SECRET_KEY   = os.getenv("PANEL_SECRET",  secrets.token_hex(32))

BASE_DIR = Path(__file__).parent

app = FastAPI(title="Center Club Admin Panel")

# Create static dir if missing (Railway deployment)
_static_dir = BASE_DIR / "static"
_static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=_static_dir), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")

# ── Simple session store (in-memory) ─────────────────────────────────────────

sessions: set = set()


def _get_session(request: Request) -> bool:
    token = request.cookies.get("session")
    return token and token in sessions


def require_auth(request: Request):
    if not _get_session(request):
        raise HTTPException(status_code=401, detail="Not authenticated")


# ── DB helpers ────────────────────────────────────────────────────────────────

def _db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def _safe_count(conn, sql, params=()):
    try:
        return conn.execute(sql, params).fetchone()[0]
    except Exception:
        return 0


def _stats():
    try:
        with _db() as conn:
            users    = _safe_count(conn, "SELECT COUNT(*) FROM users")
            bookings = _safe_count(conn, "SELECT COUNT(*) FROM bookings")
            upcoming = _safe_count(conn, "SELECT COUNT(*) FROM bookings WHERE date >= ?", (date.today().isoformat(),))
            events   = _safe_count(conn, "SELECT COUNT(*) FROM special_events")
        return {"users": users, "bookings": bookings, "upcoming": upcoming, "events": events}
    except Exception as e:
        return {"users": 0, "bookings": 0, "upcoming": 0, "events": 0, "error": str(e)}


# ── Auth routes ───────────────────────────────────────────────────────────────

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    if _get_session(request):
        return RedirectResponse("/", status_code=302)
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@app.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    if username == ADMIN_USER and password == ADMIN_PASS:
        token = secrets.token_hex(32)
        sessions.add(token)
        resp = RedirectResponse("/", status_code=302)
        resp.set_cookie("session", token, httponly=True, max_age=86400)
        return resp
    return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid credentials"})


@app.get("/logout")
async def logout(request: Request):
    token = request.cookies.get("session")
    sessions.discard(token)
    resp = RedirectResponse("/login", status_code=302)
    resp.delete_cookie("session")
    return resp


# ── Dashboard ─────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    if not _get_session(request):
        return RedirectResponse("/login", status_code=302)
    stats = _stats()
    db_ok = os.path.exists(DB_PATH)
    return templates.TemplateResponse("dashboard.html", {
        "request": request, "stats": stats,
        "db_path": DB_PATH, "db_ok": db_ok
    })


# ── Users ─────────────────────────────────────────────────────────────────────

@app.get("/users", response_class=HTMLResponse)
async def users_page(request: Request):
    if not _get_session(request):
        return RedirectResponse("/login", status_code=302)
    users = []
    try:
        with _db() as conn:
            rows = conn.execute(
                "SELECT user_id, username, lang, first_seen FROM users ORDER BY first_seen DESC"
            ).fetchall()
            users = [dict(r) for r in rows]
    except Exception:
        pass
    return templates.TemplateResponse("users.html", {"request": request, "users": users})


# ── Bookings ──────────────────────────────────────────────────────────────────

@app.get("/bookings", response_class=HTMLResponse)
async def bookings_page(request: Request, filter_date: str = ""):
    if not _get_session(request):
        return RedirectResponse("/login", status_code=302)
    bookings = []
    try:
        with _db() as conn:
            if filter_date:
                rows = conn.execute(
                    "SELECT * FROM bookings WHERE date = ? ORDER BY date, start_time",
                    (filter_date,)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM bookings ORDER BY date DESC, start_time"
                ).fetchall()
            bookings = [dict(r) for r in rows]
    except Exception:
        pass
    return templates.TemplateResponse("bookings.html", {
        "request": request, "bookings": bookings, "filter_date": filter_date
    })


@app.post("/bookings/{booking_id}/delete")
async def delete_booking(request: Request, booking_id: int):
    if not _get_session(request):
        return RedirectResponse("/login", status_code=302)
    with _db() as conn:
        conn.execute("DELETE FROM bookings WHERE id = ?", (booking_id,))
        conn.execute("DELETE FROM reminder_sent WHERE booking_id = ?", (booking_id,))
    return RedirectResponse("/bookings", status_code=302)


# ── Special Events ────────────────────────────────────────────────────────────

@app.get("/events", response_class=HTMLResponse)
async def events_page(request: Request):
    if not _get_session(request):
        return RedirectResponse("/login", status_code=302)
    events = []
    try:
        with _db() as conn:
            rows = conn.execute(
                "SELECT * FROM special_events ORDER BY event_date"
            ).fetchall()
            events = [dict(r) for r in rows]
    except Exception:
        pass
    return templates.TemplateResponse("events.html", {"request": request, "events": events})


@app.post("/events/create")
async def create_event(
    request: Request,
    title: str = Form(...),
    event_date: str = Form(...),
    event_time: str = Form(""),
    location: str = Form(...),
    description: str = Form(""),
):
    if not _get_session(request):
        return RedirectResponse("/login", status_code=302)
    with _db() as conn:
        conn.execute(
            "INSERT INTO special_events (title, event_date, event_time, location, description) VALUES (?,?,?,?,?)",
            (title, event_date, event_time, location, description)
        )
    return RedirectResponse("/events", status_code=302)


@app.post("/events/{event_id}/delete")
async def delete_event(request: Request, event_id: int):
    if not _get_session(request):
        return RedirectResponse("/login", status_code=302)
    with _db() as conn:
        conn.execute("DELETE FROM special_events WHERE id = ?", (event_id,))
    return RedirectResponse("/events", status_code=302)


@app.post("/events/{event_id}/edit")
async def edit_event(
    request: Request,
    event_id: int,
    title: str = Form(...),
    event_date: str = Form(...),
    event_time: str = Form(""),
    location: str = Form(...),
    description: str = Form(""),
):
    if not _get_session(request):
        return RedirectResponse("/login", status_code=302)
    with _db() as conn:
        conn.execute(
            "UPDATE special_events SET title=?, event_date=?, event_time=?, location=?, description=? WHERE id=?",
            (title, event_date, event_time, location, description, event_id)
        )
    return RedirectResponse("/events", status_code=302)


# ── Notifications API ─────────────────────────────────────────────────────────

@app.get("/notifications", response_class=HTMLResponse)
async def notifications_page(request: Request):
    if not _get_session(request):
        return RedirectResponse("/login", status_code=302)
    return templates.TemplateResponse("notifications.html", {"request": request})


@app.post("/api/notify/all")
async def notify_all(request: Request):
    """Queue a broadcast message."""
    if not _get_session(request):
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    data = await request.json()
    message = data.get("message", "").strip()
    if not message:
        raise HTTPException(400, "Message is required")
    db_dir = os.path.dirname(os.path.abspath(DB_PATH)) or "."
    flag_path = os.path.join(db_dir, "pending_broadcast.txt")
    try:
        with open(flag_path, "w", encoding="utf-8") as f:
            f.write(message)
    except Exception as e:
        raise HTTPException(500, f"Could not write broadcast file: {e}")
    return JSONResponse({"status": "ok", "message": "Broadcast queued"})


@app.post("/api/clear-notifications")
async def clear_notifications_api(request: Request):
    """Delete all pending notification messages via Telegram API."""
    if not _get_session(request):
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    if not BOT_TOKEN:
        raise HTTPException(500, "BOT_TOKEN not configured")

    import httpx
    notifications = []
    try:
        conn = _db()
        rows = conn.execute("SELECT user_id, chat_id, message_id FROM pending_notifications").fetchall()
        notifications = [dict(r) for r in rows]
        conn.close()
    except Exception as e:
        raise HTTPException(500, f"DB error: {e}")

    deleted = 0
    failed = 0
    async with httpx.AsyncClient() as client:
        for n in notifications:
            try:
                resp = await client.post(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/deleteMessage",
                    json={"chat_id": n["chat_id"], "message_id": n["message_id"]},
                    timeout=5
                )
                if resp.status_code == 200:
                    deleted += 1
                else:
                    failed += 1
            except Exception:
                failed += 1

    # Clear from DB
    try:
        conn = _db()
        conn.execute("DELETE FROM pending_notifications")
        conn.commit()
        conn.close()
    except Exception:
        pass

    return JSONResponse({
        "status": "ok",
        "deleted": deleted,
        "failed": failed,
        "total": len(notifications)
    })


@app.get("/api/notifications/count")
async def notifications_count(request: Request):
    """Get count of pending notifications."""
    if not _get_session(request):
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    try:
        conn = _db()
        count = conn.execute("SELECT COUNT(*) FROM pending_notifications").fetchone()[0]
        conn.close()
        return JSONResponse({"count": count})
    except Exception:
        return JSONResponse({"count": 0})




@app.post("/api/reset-bot")
async def reset_bot(request: Request):
    """Trigger a safe soft reset of bot runtime state."""
    if not _get_session(request):
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    try:
        db_dir = os.path.dirname(os.path.abspath(DB_PATH)) or "."
        flag_path = os.path.join(db_dir, "bot_reset.flag")
        from datetime import datetime as _dt
        with open(flag_path, "w") as f:
            f.write(_dt.utcnow().isoformat())
        return JSONResponse({
            "status": "ok",
            "message": "Reset flag written. Bot will reset on next user interaction.",
        })
    except Exception as e:
        raise HTTPException(500, f"Could not write reset flag: {e}")

@app.get("/api/stats")
async def api_stats(request: Request):
    if not _get_session(request):
        return RedirectResponse("/login", status_code=302)
    return JSONResponse(_stats())
