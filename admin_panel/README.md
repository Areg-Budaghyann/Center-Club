# Center Club Admin Panel

Web-based admin panel for the Center Club Telegram Bot.

## Setup

### 1. Install dependencies
```bash
cd admin_panel
pip install -r requirements.txt
```

### 2. Environment variables
```bash
export DATABASE_PATH=/data/office.db   # path to bot's SQLite DB
export PANEL_USER=admin                # login username
export PANEL_PASS=yourpassword         # login password
export PANEL_SECRET=randomsecret       # session secret
```

### 3. Run locally
```bash
uvicorn main:app --host 0.0.0.0 --port 8080 --reload
```
Open: http://localhost:8080

---

## Deploy on Railway (separate service)

1. Create a **new service** in Railway (same project)
2. Point it to the same GitHub repo, folder: `admin_panel`
3. Add a `Procfile` in admin_panel/:
   ```
   web: uvicorn main:app --host 0.0.0.0 --port $PORT
   ```
4. Set variables:
   ```
   DATABASE_PATH=/data/office.db
   PANEL_USER=admin
   PANEL_PASS=yourpassword
   PANEL_SECRET=randomsecret
   PORT=8080
   ```
5. **Mount the same volume** at `/data` — so it reads the bot's database

---

## Features
- 🔐 Login with username/password
- 📊 Dashboard with stats
- 👥 Users list
- 📅 Bookings with date filter + delete
- 🎉 Special Events — create / edit / delete
- 📢 Broadcast notification to all users
