# 🏢 Office Booking Bot

A production-quality Telegram bot for scheduling a shared office space among a group of friends.

---

## Features

| Feature | Description |
|---|---|
| 📅 Book office | 4-step flow: date → time → duration → title |
| 📊 View schedule | Weekly or monthly view |
| 🟢 Free time | Available slots for any day |
| 📌 My bookings | View, edit, or cancel your reservations |
| ⚠️ Conflict detection | Prevents double bookings, shows the clash |
| ⏰ Reminders | Automatic DM 1 hour before your event |
| 📢 Group notifications | Posts new bookings to a group chat |

---

## Project Structure

```
office_bot/
├── bot.py                   # Entry point
├── config.py                # Env vars & constants
├── database.py              # All SQL queries
├── models.py                # Booking dataclass
├── handlers/
│   ├── start.py             # /start, main menu, help
│   ├── booking.py           # Multi-step booking flow
│   ├── schedule.py          # View schedule & free time
│   └── mybookings.py        # Manage own bookings
├── services/
│   ├── booking_service.py   # Conflict detection, CRUD logic
│   └── schedule_service.py  # Weekly/monthly views, free slots
├── scheduler/
│   └── reminders.py         # APScheduler 1-hour reminders
├── requirements.txt
├── Dockerfile
├── railway.toml
└── Procfile
```

---

## Installation

### Prerequisites

- Python 3.11+
- A Telegram bot token from [@BotFather](https://t.me/BotFather)

### 1. Clone / download the project

```bash
git clone <your-repo-url>
cd office_bot
```

### 2. Create a virtual environment

```bash
python -m venv venv
source venv/bin/activate        # Linux/macOS
venv\Scripts\activate           # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env`:

```env
BOT_TOKEN=7123456789:ABCdef...        # from @BotFather
GROUP_CHAT_ID=-1001234567890          # optional: group for notifications
DATABASE_PATH=office.db
OFFICE_OPEN=10
OFFICE_CLOSE=23
```

**Getting GROUP_CHAT_ID:**
1. Add the bot to your group.
2. Send any message in the group.
3. Visit `https://api.telegram.org/bot<TOKEN>/getUpdates` and look for `"chat":{"id":-100...}`.

---

## Running Locally

```bash
python bot.py
```

The bot starts in **polling mode** (no WEBHOOK_URL set). You'll see:

```
2026-03-15 12:00:00 | INFO     | bot | Starting polling…
2026-03-15 12:00:00 | INFO     | scheduler.reminders | Reminder scheduler started (interval: 1 min)
```

Open Telegram, find your bot, send `/start`.

---

## Running with Docker (locally)

```bash
docker build -t office-bot .
docker run --env-file .env -v $(pwd)/data:/data office-bot
```

The SQLite file will be persisted in `./data/office.db`.

---

## Deployment

### Option A — Railway (recommended, free tier available)

1. Push your code to a GitHub repository.
2. Go to [railway.app](https://railway.app) → New Project → Deploy from GitHub.
3. Add environment variables in the Railway dashboard:
   - `BOT_TOKEN`
   - `GROUP_CHAT_ID` (optional)
   - `WEBHOOK_URL` — set to your Railway public URL, e.g. `https://office-bot-production.up.railway.app`
   - `DATABASE_PATH=/data/office.db`
4. Add a **Volume** mounted at `/data` so the SQLite file survives restarts.
5. Deploy. Railway uses `railway.toml` → `Dockerfile` automatically.

> **Note:** When `WEBHOOK_URL` is set, the bot switches from polling to webhook mode automatically.

### Option B — Heroku

```bash
heroku create my-office-bot
heroku config:set BOT_TOKEN=...
heroku config:set GROUP_CHAT_ID=...
heroku config:set WEBHOOK_URL=https://my-office-bot.herokuapp.com
git push heroku main
heroku ps:scale worker=1
```

> Heroku's ephemeral filesystem loses the SQLite file on restart.  
> For production, swap SQLite for PostgreSQL using `psycopg2` and update `database.py`.

### Option C — VPS / any server

```bash
# Install
git clone <repo> && cd office_bot
pip install -r requirements.txt
cp .env.example .env && nano .env

# Run with systemd
sudo nano /etc/systemd/system/office-bot.service
```

`office-bot.service`:
```ini
[Unit]
Description=Office Booking Bot
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/office_bot
EnvironmentFile=/home/ubuntu/office_bot/.env
ExecStart=/home/ubuntu/office_bot/venv/bin/python bot.py
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now office-bot
sudo journalctl -fu office-bot
```

---

## Example Bot Usage

```
User: /start

Bot: 👋 Office Booking Bot
     Reserve a time slot in our shared office.
     What would you like to do?
     [📅 Book office] [📊 View schedule]
     [📌 My bookings] [🟢 Free time] [ℹ️ Help]

─── Booking flow ────────────────────────────

User: [📅 Book office]
Bot:  Step 1 of 4 — Choose a date:
      [Today 15 Mar] [Sun 16 Mar] [Mon 17 Mar]
      [Tue 18 Mar]   [Wed 19 Mar] [Thu 20 Mar]
      ...

User: [Sat 21 Mar]
Bot:  📅 2026-03-21
      Step 2 of 4 — Choose start time:
      [10:00] [11:00] [12:00] [13:00]
      [14:00] [15:00] [16:00] [17:00]
      ...

User: [15:00]
Bot:  📅 2026-03-21 | 🕐 15:00
      Step 3 of 4 — Choose duration:
      [1h] [2h] [3h] [4h] [5h] [6h]

User: [3h]
Bot:  Step 4 of 4 — Enter event title:
      Type the name of your event (e.g. Board Games)

User: Board Games
Bot:  ✅ Confirm booking:
      📋 Title: Board Games
      📅 Date:  2026-03-21
      🕐 Time:  15:00 – 18:00 (3h)
      👤 You:   @areg
      [✅ Confirm] [✖ Cancel]

User: [✅ Confirm]
Bot:  🎉 Booking confirmed!
      📋 Board Games
      📅 2026-03-21
      🕐 15:00 – 18:00 (3h)
      👤 @areg

─── Group chat ──────────────────────────────

Bot → group:
      📢 New office booking
      📅 Saturday, Mar 21
      🕐 15:00 – 18:00
      📋 Board Games
      👤 Organiser: @areg

─── Reminder (1 hour before) ────────────────

Bot → user DM:
      ⏰ Reminder — your booking starts in ~60 minutes!
      📋 Board Games
      📅 2026-03-21
      🕐 15:00 – 18:00 (3h)
      👤 @areg

─── Conflict example ────────────────────────

User tries to book 16:00–19:00 on same day:
Bot:  ❌ Time conflict!
      That slot overlaps with an existing booking:
      15:00 – 18:00 | Board Games (@areg)
      Please try a different time.

─── Free time ───────────────────────────────

User: [🟢 Free time] → [Today]
Bot:  🟢 Free slots on Sunday, Mar 15:
        10:00 – 15:00
        18:00 – 23:00
```

---

## Configuration Reference

| Variable | Default | Description |
|---|---|---|
| `BOT_TOKEN` | *required* | Telegram bot token |
| `GROUP_CHAT_ID` | `""` | Group chat for notifications (omit to disable) |
| `DATABASE_PATH` | `office.db` | SQLite file path |
| `OFFICE_OPEN` | `10` | Opening hour (inclusive) |
| `OFFICE_CLOSE` | `23` | Closing hour (exclusive) |
| `WEBHOOK_URL` | `""` | Set for webhook mode (production) |
| `PORT` | `8443` | Webhook listen port |
