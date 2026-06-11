"""
Young Life Armenia — Streamlit Admin Panel
Run: streamlit run admin_panel/streamlit_app.py
"""

import os
import sys
import sqlite3
import io
import json
from datetime import datetime, date, timedelta
from pathlib import Path

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
from dotenv import load_dotenv

# ── env / paths ────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent
load_dotenv(ROOT / ".env")

DATABASE_PATH = os.getenv("DATABASE_PATH", "office_test.db")
if not os.path.isabs(DATABASE_PATH):
    DATABASE_PATH = str(ROOT / DATABASE_PATH)

PANEL_USER = os.getenv("PANEL_USER", "admin")
PANEL_PASS = os.getenv("PANEL_PASS", "changeme")
BOT_TOKEN  = os.getenv("BOT_TOKEN", "")

CLUBS: dict[str, str] = {
    "abovyan":   "Abovyan",
    "joyful":    "Joyful",
    "ararat":    "Ararat",
    "eghvard":   "Eghvard",
    "club36":    "Club 36",
    "davtashen": "Davtashen",
    "mix":       "Mix",
    "kievyan":   "Kievyan",
    "monument":  "Monument",
    "shengavit": "Shengavit",
    "hrazdan":   "Hrazdan",
    "avan":      "Avan",
    "unity":     "Unity",
    "kvartall":  "Kvartall",
    "revive":    "Revive",
    "centerclub":"Center Club",
    "stage":     "Stage",
}

# ── page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="YL Armenia Admin",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── brand CSS ──────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* Sidebar */
[data-testid="stSidebar"] {
    background: #003F60 !important;
}
[data-testid="stSidebar"] * {
    color: #ffffff !important;
}
[data-testid="stSidebar"] .stRadio label {
    color: #ffffff !important;
    font-size: 15px;
}
[data-testid="stSidebar"] hr {
    border-color: rgba(255,255,255,0.3);
}

/* Headings */
h1, h2, h3 { color: #003F60 !important; }

/* Metric cards accent */
[data-testid="metric-container"] {
    background: #f4f9ff;
    border-left: 4px solid #98C33D;
    border-radius: 6px;
    padding: 12px !important;
}

/* Buttons */
.stButton > button {
    background: #003F60;
    color: white;
    border-radius: 6px;
    border: none;
}
.stButton > button:hover {
    background: #98C33D;
    color: #003F60;
}

/* Success / error */
.stSuccess { border-left: 4px solid #98C33D; }
.stError   { border-left: 4px solid #d9534f; }

/* Table */
[data-testid="stDataFrame"] { border: 1px solid #e0e0e0; border-radius: 6px; }

/* Top logo bar */
.yla-header {
    background: #003F60;
    color: white;
    padding: 10px 20px;
    border-radius: 8px;
    margin-bottom: 20px;
    display: flex;
    align-items: center;
    gap: 12px;
}
.yla-header h2 { color: #98C33D !important; margin: 0; }
</style>
""", unsafe_allow_html=True)

# ── db helpers ─────────────────────────────────────────────────────────────────

def get_conn():
    conn = sqlite3.connect(DATABASE_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def query_df(sql: str, params=()) -> pd.DataFrame:
    with get_conn() as conn:
        return pd.read_sql_query(sql, conn, params=params)


def execute(sql: str, params=()):
    with get_conn() as conn:
        conn.execute(sql, params)
        conn.commit()


def club_name(cid: str) -> str:
    return CLUBS.get(cid, cid or "—")


# ── auth ───────────────────────────────────────────────────────────────────────

def login_page():
    st.markdown("""
    <div class='yla-header'>
        <div>
            <h2>Young Life Armenia</h2>
            <p style='margin:0;color:#cce0f0;font-size:13px;'>Office Booking Admin Panel</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        st.subheader("🔐 Sign In")
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Login", use_container_width=True)

        if submitted:
            if username == PANEL_USER and password == PANEL_PASS:
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("Invalid credentials.")


def require_auth():
    if not st.session_state.get("authenticated"):
        login_page()
        st.stop()

# ── sidebar nav ────────────────────────────────────────────────────────────────

PAGES = [
    "📊 Dashboard",
    "👥 Users",
    "📅 Bookings",
    "🏢 Clubs",
    "🎉 Special Events",
    "📨 Broadcast",
    "⚙️ Settings",
]


def sidebar():
    with st.sidebar:
        st.markdown("## 🏢 YL Armenia\n*Admin Panel*")
        st.divider()
        page = st.radio("Navigation", PAGES, label_visibility="collapsed")
        st.divider()
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.clear()
            st.rerun()
    return page

# ══════════════════════════════════════════════════════════════════════════════
# PAGE 1 — DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════

def page_dashboard():
    st.title("📊 Dashboard")

    today_str = date.today().isoformat()

    with st.spinner("Loading metrics…"):
        total_users    = query_df("SELECT COUNT(*) AS n FROM users").iloc[0]["n"]
        total_bookings = query_df("SELECT COUNT(*) AS n FROM bookings").iloc[0]["n"]
        active_bk      = query_df("SELECT COUNT(*) AS n FROM bookings WHERE date >= ?", (today_str,)).iloc[0]["n"]
        total_clubs    = len(CLUBS)
        total_events   = query_df("SELECT COUNT(*) AS n FROM special_events").iloc[0]["n"]

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("👥 Total Users",    total_users)
    c2.metric("📅 Total Bookings", total_bookings)
    c3.metric("✅ Active Bookings", active_bk, help="Today and future")
    c4.metric("🏢 Clubs",          total_clubs)
    c5.metric("🎉 Special Events", total_events)

    st.divider()

    col_left, col_right = st.columns(2)

    # ── Bar chart: bookings per club ──────────────────────────────────────────
    with col_left:
        st.subheader("Bookings per Club")
        df_clubs = query_df("""
            SELECT club_id, COUNT(*) AS bookings
            FROM bookings GROUP BY club_id ORDER BY bookings DESC
        """)
        df_clubs["Club"] = df_clubs["club_id"].apply(club_name)
        fig = px.bar(
            df_clubs, x="Club", y="bookings",
            color_discrete_sequence=["#003F60"],
            labels={"bookings": "Bookings"},
        )
        fig.update_layout(margin=dict(t=20, b=60), height=320)
        st.plotly_chart(fig, use_container_width=True)

    # ── Line chart: bookings last 30 days ─────────────────────────────────────
    with col_right:
        st.subheader("Bookings — Last 30 Days")
        cutoff = (date.today() - timedelta(days=30)).isoformat()
        df_days = query_df("""
            SELECT date, COUNT(*) AS bookings
            FROM bookings WHERE date >= ?
            GROUP BY date ORDER BY date
        """, (cutoff,))
        if not df_days.empty:
            fig2 = px.line(
                df_days, x="date", y="bookings",
                color_discrete_sequence=["#98C33D"],
                labels={"date": "Date", "bookings": "Bookings"},
            )
            fig2.update_layout(margin=dict(t=20, b=40), height=320)
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("No bookings in the last 30 days.")

    st.divider()

    # ── Today's bookings ─────────────────────────────────────────────────────
    st.subheader(f"Today's Bookings — {today_str}")
    df_today = query_df("""
        SELECT b.club_id, b.username, b.title, b.start_time, b.duration, b.created_at
        FROM bookings b
        WHERE b.date = ?
        ORDER BY b.start_time
    """, (today_str,))

    if df_today.empty:
        st.info("No bookings today.")
    else:
        df_today["Club"]       = df_today["club_id"].apply(club_name)
        df_today["User"]       = df_today["username"].apply(lambda u: f"@{u}" if u else "—")
        df_today["Start"]      = df_today["start_time"]
        df_today["End"]        = df_today.apply(
            lambda r: (datetime.strptime(r["start_time"], "%H:%M") + timedelta(hours=r["duration"])).strftime("%H:%M"),
            axis=1,
        )
        df_today["Created at"] = df_today["created_at"].str[:16]
        st.dataframe(
            df_today[["Club", "User", "title", "Start", "End", "Created at"]].rename(columns={"title": "Title"}),
            use_container_width=True, hide_index=True,
        )

# ══════════════════════════════════════════════════════════════════════════════
# PAGE 2 — USERS
# ══════════════════════════════════════════════════════════════════════════════

def page_users():
    st.title("👥 Users")

    df = query_df("SELECT user_id, username, lang, club_id, first_seen FROM users ORDER BY first_seen DESC")
    df["Club"]      = df["club_id"].apply(club_name)
    df["first_seen"] = df["first_seen"].str[:16]

    # ── filters ──────────────────────────────────────────────────────────────
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        search = st.text_input("🔍 Search by username or user_id", placeholder="e.g. john or 123456")
    with col2:
        club_opts = ["All"] + sorted(CLUBS.values())
        club_filter = st.selectbox("Filter by club", club_opts)
    with col3:
        st.markdown("<br>", unsafe_allow_html=True)
        export_btn = st.button("⬇️ Export CSV", use_container_width=True)

    if search:
        mask = (
            df["username"].str.contains(search, case=False, na=False) |
            df["user_id"].astype(str).str.contains(search, na=False)
        )
        df = df[mask]
    if club_filter != "All":
        df = df[df["Club"] == club_filter]

    if export_btn:
        csv = df.to_csv(index=False).encode()
        st.download_button("Download users.csv", csv, "users.csv", "text/csv")

    st.caption(f"{len(df)} user(s) found")
    st.dataframe(
        df[["user_id", "username", "Club", "lang", "first_seen"]].rename(
            columns={"lang": "Language", "first_seen": "First Seen"}
        ),
        use_container_width=True, hide_index=True,
    )

    st.divider()

    # ── per-user actions ──────────────────────────────────────────────────────
    st.subheader("User Actions")
    col_a, col_b = st.columns(2)
    with col_a:
        uid_input = st.number_input("User ID", min_value=1, step=1, format="%d", key="uid_action")
    with col_b:
        st.markdown("<br>", unsafe_allow_html=True)
        action_col1, action_col2 = st.columns(2)

        with action_col1:
            if st.button("🔄 Reset Club Auth", use_container_width=True):
                execute("UPDATE users SET club_id = '' WHERE user_id = ?", (int(uid_input),))
                st.success(f"Club auth reset for user {uid_input}.")

        with action_col2:
            if st.button("🗑️ Delete User", use_container_width=True, type="primary"):
                st.session_state["confirm_delete_user"] = int(uid_input)

    if st.session_state.get("confirm_delete_user"):
        uid_del = st.session_state["confirm_delete_user"]
        st.warning(f"Delete user {uid_del} AND all their bookings? This cannot be undone.")
        cc1, cc2 = st.columns(2)
        with cc1:
            if st.button("✅ Confirm Delete", key="confirm_del_user_yes"):
                execute("DELETE FROM bookings WHERE user_id = ?", (uid_del,))
                execute("DELETE FROM users WHERE user_id = ?", (uid_del,))
                del st.session_state["confirm_delete_user"]
                st.success(f"User {uid_del} deleted.")
                st.rerun()
        with cc2:
            if st.button("Cancel", key="confirm_del_user_no"):
                del st.session_state["confirm_delete_user"]
                st.rerun()

    # ── user's bookings ───────────────────────────────────────────────────────
    st.subheader("View User's Bookings")
    uid_view = st.number_input("User ID to view", min_value=1, step=1, format="%d", key="uid_view")
    if st.button("Show Bookings"):
        df_ub = query_df("""
            SELECT id, club_id, title, date, start_time, duration, created_at
            FROM bookings WHERE user_id = ? ORDER BY date DESC
        """, (int(uid_view),))
        if df_ub.empty:
            st.info("No bookings found.")
        else:
            df_ub["Club"] = df_ub["club_id"].apply(club_name)
            df_ub["End"]  = df_ub.apply(
                lambda r: (datetime.strptime(r["start_time"], "%H:%M") + timedelta(hours=r["duration"])).strftime("%H:%M"),
                axis=1,
            )
            st.dataframe(
                df_ub[["id", "Club", "title", "date", "start_time", "End", "duration", "created_at"]].rename(
                    columns={"title": "Title", "date": "Date", "start_time": "Start",
                             "duration": "Dur (h)", "created_at": "Created"}
                ),
                use_container_width=True, hide_index=True,
            )

# ══════════════════════════════════════════════════════════════════════════════
# PAGE 3 — BOOKINGS
# ══════════════════════════════════════════════════════════════════════════════

def page_bookings():
    st.title("📅 Bookings")

    # ── filters ──────────────────────────────────────────────────────────────
    col1, col2, col3, col4 = st.columns([2, 1.5, 1.5, 1])
    with col1:
        username_filter = st.text_input("🔍 Filter by username")
    with col2:
        club_opts = ["All"] + sorted(CLUBS.values())
        club_filter = st.selectbox("Club", club_opts, key="bk_club")
    with col3:
        date_from = st.date_input("From", value=None, key="bk_from")
        date_to   = st.date_input("To",   value=None, key="bk_to")
    with col4:
        st.markdown("<br>", unsafe_allow_html=True)
        export_btn = st.button("⬇️ Export CSV", use_container_width=True, key="bk_export")

    # ── query ─────────────────────────────────────────────────────────────────
    sql = "SELECT id, club_id, user_id, username, title, date, start_time, duration, created_at FROM bookings WHERE 1=1"
    params: list = []

    if username_filter:
        sql += " AND username LIKE ?"
        params.append(f"%{username_filter}%")
    if club_filter != "All":
        club_id_filter = next((k for k, v in CLUBS.items() if v == club_filter), None)
        if club_id_filter:
            sql += " AND club_id = ?"
            params.append(club_id_filter)
    if date_from:
        sql += " AND date >= ?"
        params.append(date_from.isoformat())
    if date_to:
        sql += " AND date <= ?"
        params.append(date_to.isoformat())

    sql += " ORDER BY date DESC, start_time"

    df = query_df(sql, tuple(params))

    if not df.empty:
        df["Club"]     = df["club_id"].apply(club_name)
        df["User"]     = df["username"].apply(lambda u: f"@{u}" if u else str(df.loc[df["username"] == u, "user_id"].values[0]) if u == "" else "—")
        df["End"]      = df.apply(
            lambda r: (datetime.strptime(r["start_time"], "%H:%M") + timedelta(hours=r["duration"])).strftime("%H:%M"),
            axis=1,
        )
        df["Duration"] = df["duration"].apply(
            lambda d: f"{int(d)}h" if d == int(d) else f"{int(d)}h {int((d % 1) * 60)}m"
        )
        df["Created"]  = df["created_at"].str[:16]

    if export_btn and not df.empty:
        csv = df.to_csv(index=False).encode()
        st.download_button("Download bookings.csv", csv, "bookings.csv", "text/csv")

    st.caption(f"{len(df)} booking(s) found")

    display_cols = ["id", "Club", "username", "title", "date", "start_time", "End", "Duration", "Created"]
    rename_map   = {"username": "User", "title": "Title", "date": "Date",
                    "start_time": "Start", "id": "ID"}

    if df.empty:
        st.info("No bookings match the filters.")
    else:
        st.dataframe(
            df[display_cols].rename(columns=rename_map),
            use_container_width=True, hide_index=True,
        )

    # ── delete booking ────────────────────────────────────────────────────────
    st.divider()
    st.subheader("Delete a Booking")
    bk_id = st.number_input("Booking ID", min_value=1, step=1, format="%d")
    if st.button("🗑️ Delete Booking", type="primary"):
        st.session_state["confirm_delete_bk"] = int(bk_id)

    if st.session_state.get("confirm_delete_bk"):
        bid = st.session_state["confirm_delete_bk"]
        row = query_df("SELECT * FROM bookings WHERE id = ?", (bid,))
        if row.empty:
            st.error(f"Booking {bid} not found.")
            del st.session_state["confirm_delete_bk"]
        else:
            r = row.iloc[0]
            st.warning(f"Delete booking #{bid}: **{r['title']}** by @{r['username']} on {r['date']}?")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("✅ Confirm", key="confirm_bk_yes"):
                    execute("DELETE FROM reminder_sent WHERE booking_id = ?", (bid,))
                    execute("DELETE FROM bookings WHERE id = ?", (bid,))
                    del st.session_state["confirm_delete_bk"]
                    st.success(f"Booking {bid} deleted.")
                    st.rerun()
            with c2:
                if st.button("Cancel", key="confirm_bk_no"):
                    del st.session_state["confirm_delete_bk"]
                    st.rerun()

    # ── calendar view ─────────────────────────────────────────────────────────
    st.divider()
    st.subheader("📆 Calendar View")
    cal_col1, cal_col2 = st.columns(2)
    with cal_col1:
        cal_club_name = st.selectbox("Club for calendar", sorted(CLUBS.values()), key="cal_club")
    with cal_col2:
        cal_month = st.date_input("Month", value=date.today().replace(day=1), key="cal_month")

    cal_club_id = next((k for k, v in CLUBS.items() if v == cal_club_name), None)
    if cal_club_id and cal_month:
        month_start = cal_month.replace(day=1)
        if cal_month.month == 12:
            month_end = cal_month.replace(year=cal_month.year + 1, month=1, day=1)
        else:
            month_end = cal_month.replace(month=cal_month.month + 1, day=1)

        df_cal = query_df("""
            SELECT date, COUNT(*) AS count FROM bookings
            WHERE club_id = ? AND date >= ? AND date < ?
            GROUP BY date
        """, (cal_club_id, month_start.isoformat(), month_end.isoformat()))

        if df_cal.empty:
            st.info(f"No bookings for {cal_club_name} in {cal_month.strftime('%B %Y')}.")
        else:
            df_cal["date_dt"] = pd.to_datetime(df_cal["date"])
            fig_cal = go.Figure(go.Scatter(
                x=df_cal["date_dt"], y=df_cal["count"],
                mode="markers+lines",
                marker=dict(size=12, color="#98C33D"),
                line=dict(color="#003F60"),
                text=df_cal["count"].apply(lambda n: f"{n} booking(s)"),
            ))
            fig_cal.update_layout(
                title=f"{cal_club_name} — {cal_month.strftime('%B %Y')}",
                xaxis_title="Date", yaxis_title="Bookings",
                height=300, margin=dict(t=40, b=40),
            )
            st.plotly_chart(fig_cal, use_container_width=True)

# ══════════════════════════════════════════════════════════════════════════════
# PAGE 4 — CLUBS
# ══════════════════════════════════════════════════════════════════════════════

def page_clubs():
    st.title("🏢 Clubs")

    # ── summary table ─────────────────────────────────────────────────────────
    rows = []
    for cid, cname in CLUBS.items():
        members  = query_df("SELECT COUNT(*) AS n FROM users WHERE club_id = ?", (cid,)).iloc[0]["n"]
        total_bk = query_df("SELECT COUNT(*) AS n FROM bookings WHERE club_id = ?", (cid,)).iloc[0]["n"]
        last_bk  = query_df("SELECT MAX(date) AS d FROM bookings WHERE club_id = ?", (cid,)).iloc[0]["d"] or "—"
        rows.append({"Club ID": cid, "Club Name": cname, "Members": members,
                     "Total Bookings": total_bk, "Last Booking": last_bk})

    df_clubs = pd.DataFrame(rows).sort_values("Total Bookings", ascending=False).reset_index(drop=True)
    st.dataframe(df_clubs, use_container_width=True, hide_index=True)

    # ── activity bar ──────────────────────────────────────────────────────────
    fig = px.bar(
        df_clubs, x="Club Name", y="Total Bookings",
        color="Total Bookings", color_continuous_scale=["#cce0f0", "#003F60"],
        title="Most Active Clubs",
    )
    fig.update_layout(height=350, margin=dict(t=40, b=60))
    st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # ── club drill-down ───────────────────────────────────────────────────────
    st.subheader("Club Detail")
    selected_club_name = st.selectbox("Select club", sorted(CLUBS.values()), key="club_detail")
    selected_club_id   = next((k for k, v in CLUBS.items() if v == selected_club_name), None)

    if selected_club_id:
        tab1, tab2, tab3 = st.tabs(["👥 Members", "📅 Bookings", "📊 Stats"])

        with tab1:
            df_members = query_df(
                "SELECT user_id, username, lang, first_seen FROM users WHERE club_id = ? ORDER BY first_seen DESC",
                (selected_club_id,)
            )
            st.caption(f"{len(df_members)} member(s)")
            st.dataframe(df_members.rename(columns={"lang": "Language", "first_seen": "First Seen"}),
                         use_container_width=True, hide_index=True)

        with tab2:
            df_bk = query_df("""
                SELECT id, username, title, date, start_time, duration, created_at
                FROM bookings WHERE club_id = ? ORDER BY date DESC
            """, (selected_club_id,))
            st.caption(f"{len(df_bk)} booking(s)")
            if not df_bk.empty:
                df_bk["End"] = df_bk.apply(
                    lambda r: (datetime.strptime(r["start_time"], "%H:%M") + timedelta(hours=r["duration"])).strftime("%H:%M"),
                    axis=1,
                )
                st.dataframe(df_bk[["id", "username", "title", "date", "start_time", "End", "duration"]].rename(
                    columns={"username": "User", "title": "Title", "date": "Date",
                             "start_time": "Start", "duration": "Dur (h)"}),
                    use_container_width=True, hide_index=True)

        with tab3:
            total = len(df_bk) if "df_bk" in dir() else query_df(
                "SELECT COUNT(*) AS n FROM bookings WHERE club_id = ?", (selected_club_id,)).iloc[0]["n"]
            avg_dur = query_df("SELECT AVG(duration) AS a FROM bookings WHERE club_id = ?", (selected_club_id,)).iloc[0]["a"]
            c1, c2 = st.columns(2)
            c1.metric("Total Bookings", int(total))
            c2.metric("Avg Duration (h)", f"{avg_dur:.1f}" if avg_dur else "—")

            df_per_day = query_df("""
                SELECT date, COUNT(*) AS bookings FROM bookings WHERE club_id = ?
                GROUP BY date ORDER BY date
            """, (selected_club_id,))
            if not df_per_day.empty:
                fig_s = px.line(df_per_day, x="date", y="bookings",
                                color_discrete_sequence=["#98C33D"],
                                title="Bookings Over Time")
                fig_s.update_layout(height=280, margin=dict(t=40, b=40))
                st.plotly_chart(fig_s, use_container_width=True)

    # ── change club password ───────────────────────────────────────────────────
    st.divider()
    st.subheader("🔑 Change Club Password")
    pw_club_name = st.selectbox("Club", sorted(CLUBS.values()), key="pw_club")
    pw_club_id   = next((k for k, v in CLUBS.items() if v == pw_club_name), None)
    new_pw       = st.text_input("New Password", type="password")

    if st.button("Update Password"):
        if not new_pw:
            st.error("Password cannot be empty.")
        elif pw_club_id:
            env_key = f"CLUB_PASSWORD_{pw_club_id.upper().replace('CENTERCLUB', 'CENTER_CLUB')}"
            env_path = ROOT / ".env"
            lines = env_path.read_text(encoding="utf-8").splitlines()
            updated = False
            new_lines = []
            for line in lines:
                if line.startswith(f"{env_key}="):
                    new_lines.append(f"{env_key}={new_pw}")
                    updated = True
                else:
                    new_lines.append(line)
            if not updated:
                new_lines.append(f"{env_key}={new_pw}")
            env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
            st.success(f"Password for {pw_club_name} updated in .env. Restart the bot to apply.")

# ══════════════════════════════════════════════════════════════════════════════
# PAGE 5 — SPECIAL EVENTS
# ══════════════════════════════════════════════════════════════════════════════

def page_events():
    st.title("🎉 Special Events")

    # ── filters ──────────────────────────────────────────────────────────────
    col1, col2, col3 = st.columns([2, 2, 2])
    with col1:
        ev_club = st.selectbox("Filter by club", ["All"] + sorted(CLUBS.values()), key="ev_club")
    with col2:
        ev_from = st.date_input("From date", value=None, key="ev_from")
    with col3:
        ev_to   = st.date_input("To date", value=None, key="ev_to")

    sql = """
        SELECT id, club_id, title, event_date, event_time, location, description, created_by, created_at
        FROM special_events WHERE 1=1
    """
    params: list = []
    if ev_club != "All":
        cid = next((k for k, v in CLUBS.items() if v == ev_club), None)
        if cid:
            sql += " AND club_id = ?"; params.append(cid)
    if ev_from:
        sql += " AND event_date >= ?"; params.append(ev_from.isoformat())
    if ev_to:
        sql += " AND event_date <= ?"; params.append(ev_to.isoformat())
    sql += " ORDER BY event_date DESC"

    df = query_df(sql, tuple(params))
    if not df.empty:
        df["Club"]    = df["club_id"].apply(club_name)
        df["Created"] = df["created_at"].str[:16]

    st.caption(f"{len(df)} event(s) found")
    if df.empty:
        st.info("No events found.")
    else:
        st.dataframe(
            df[["id", "Club", "title", "event_date", "event_time", "location", "created_by", "Created"]].rename(
                columns={"title": "Title", "event_date": "Date", "event_time": "Time",
                         "location": "Location", "created_by": "Created By", "id": "ID"}
            ),
            use_container_width=True, hide_index=True,
        )

    # ── delete event ──────────────────────────────────────────────────────────
    st.divider()
    col_del, col_add = st.columns(2)

    with col_del:
        st.subheader("🗑️ Delete Event")
        ev_id_del = st.number_input("Event ID to delete", min_value=1, step=1, format="%d", key="ev_del_id")
        if st.button("Delete Event", type="primary", key="ev_del_btn"):
            st.session_state["confirm_del_ev"] = int(ev_id_del)

        if st.session_state.get("confirm_del_ev"):
            eid = st.session_state["confirm_del_ev"]
            ev_row = query_df("SELECT * FROM special_events WHERE id = ?", (eid,))
            if ev_row.empty:
                st.error("Event not found.")
                del st.session_state["confirm_del_ev"]
            else:
                r = ev_row.iloc[0]
                st.warning(f"Delete event #{eid}: **{r['title']}** on {r['event_date']}?")
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("✅ Confirm", key="ev_del_yes"):
                        execute("DELETE FROM special_events WHERE id = ?", (eid,))
                        del st.session_state["confirm_del_ev"]
                        st.success("Event deleted.")
                        st.rerun()
                with c2:
                    if st.button("Cancel", key="ev_del_no"):
                        del st.session_state["confirm_del_ev"]
                        st.rerun()

    with col_add:
        st.subheader("➕ Add New Event")
        with st.form("add_event_form"):
            ev_title    = st.text_input("Title *")
            ev_date     = st.date_input("Date *", value=date.today())
            ev_time     = st.text_input("Time (HH:MM)", placeholder="18:00")
            ev_loc      = st.text_input("Location")
            ev_desc     = st.text_area("Description")
            ev_club_new = st.selectbox("Club", ["(all clubs)"] + sorted(CLUBS.values()), key="ev_new_club")
            submitted   = st.form_submit_button("Create Event", use_container_width=True)

        if submitted:
            if not ev_title:
                st.error("Title is required.")
            else:
                cid_new = "" if ev_club_new == "(all clubs)" else next(
                    (k for k, v in CLUBS.items() if v == ev_club_new), ""
                )
                execute("""
                    INSERT INTO special_events (title, event_date, event_time, location, description, club_id, created_by, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (ev_title, ev_date.isoformat(), ev_time, ev_loc, ev_desc, cid_new, 0,
                      datetime.utcnow().isoformat(timespec="seconds")))
                st.success(f"Event '{ev_title}' created.")
                st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# PAGE 6 — BROADCAST MESSAGE
# ══════════════════════════════════════════════════════════════════════════════

def page_broadcast():
    st.title("📨 Broadcast Message")

    if not BOT_TOKEN:
        st.error("BOT_TOKEN not set in .env — cannot send messages.")
        return

    target_type = st.radio(
        "Send to",
        ["All users", "Specific club", "Specific user"],
        horizontal=True,
    )

    recipients: list[int] = []

    if target_type == "All users":
        df_all = query_df("SELECT user_id FROM users")
        recipients = df_all["user_id"].tolist()
        st.info(f"{len(recipients)} total users")

    elif target_type == "Specific club":
        bc_club_name = st.selectbox("Club", sorted(CLUBS.values()), key="bc_club")
        bc_club_id   = next((k for k, v in CLUBS.items() if v == bc_club_name), None)
        if bc_club_id:
            df_club = query_df("SELECT user_id FROM users WHERE club_id = ?", (bc_club_id,))
            recipients = df_club["user_id"].tolist()
            st.info(f"{len(recipients)} member(s) in {bc_club_name}")

    else:
        bc_uid = st.number_input("User ID", min_value=1, step=1, format="%d", key="bc_uid")
        recipients = [int(bc_uid)]

    message_text = st.text_area("Message", placeholder="Type your message here…", height=150)

    col_prev, col_send = st.columns([1, 2])
    with col_prev:
        if st.button("👁️ Preview"):
            if message_text:
                st.markdown("**Preview:**")
                st.info(message_text)
            else:
                st.warning("Enter a message first.")

    with col_send:
        if st.button("🚀 Send Message", type="primary"):
            if not message_text:
                st.error("Message cannot be empty.")
            elif not recipients:
                st.error("No recipients selected.")
            else:
                st.session_state["confirm_broadcast"] = {
                    "text": message_text,
                    "recipients": recipients,
                }

    if st.session_state.get("confirm_broadcast"):
        bc_data = st.session_state["confirm_broadcast"]
        st.warning(f"Send this message to **{len(bc_data['recipients'])} user(s)**?")
        st.code(bc_data["text"])
        c1, c2 = st.columns(2)
        with c1:
            if st.button("✅ Confirm Send", key="bc_confirm_yes"):
                progress = st.progress(0, text="Sending…")
                ok_count = err_count = 0
                total    = len(bc_data["recipients"])

                for i, uid in enumerate(bc_data["recipients"]):
                    try:
                        resp = requests.post(
                            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                            json={"chat_id": uid, "text": bc_data["text"], "parse_mode": "HTML"},
                            timeout=10,
                        )
                        if resp.status_code == 200:
                            ok_count += 1
                        else:
                            err_count += 1
                    except Exception:
                        err_count += 1
                    progress.progress((i + 1) / total, text=f"Sent {i + 1}/{total}…")

                del st.session_state["confirm_broadcast"]
                st.success(f"Done! ✅ {ok_count} sent, ❌ {err_count} failed.")
        with c2:
            if st.button("Cancel", key="bc_confirm_no"):
                del st.session_state["confirm_broadcast"]
                st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# PAGE 7 — SETTINGS
# ══════════════════════════════════════════════════════════════════════════════

def page_settings():
    st.title("⚙️ Settings")

    # ── env overview ─────────────────────────────────────────────────────────
    st.subheader("Environment Variables")
    env_display = {
        "DATABASE_PATH":   os.getenv("DATABASE_PATH", "office_test.db"),
        "OFFICE_OPEN":     os.getenv("OFFICE_OPEN", "10"),
        "OFFICE_CLOSE":    os.getenv("OFFICE_CLOSE", "23"),
        "PANEL_USER":      os.getenv("PANEL_USER", "admin"),
        "GROUP_CHAT_ID":   os.getenv("GROUP_CHAT_ID", "(not set)"),
        "ADMIN_IDS":       os.getenv("ADMIN_IDS", "(not set)"),
        "BOT_TOKEN":       "***" + BOT_TOKEN[-6:] if BOT_TOKEN else "(not set)",
        "PANEL_PASS":      "••••••••",
    }
    st.table(pd.DataFrame({"Variable": env_display.keys(), "Value": env_display.values()}))

    # ── database info ─────────────────────────────────────────────────────────
    st.subheader("Database")
    db_path = Path(DATABASE_PATH)
    col1, col2 = st.columns(2)
    col1.metric("Path", str(db_path))
    size_kb = db_path.stat().st_size / 1024 if db_path.exists() else 0
    col2.metric("Size", f"{size_kb:.1f} KB")

    st.subheader("Database Stats")
    stat_rows = []
    for tbl in ["bookings", "users", "special_events", "reminder_sent", "pending_notifications", "event_reminder_sent"]:
        try:
            n = query_df(f"SELECT COUNT(*) AS n FROM {tbl}").iloc[0]["n"]
            stat_rows.append({"Table": tbl, "Rows": int(n)})
        except Exception:
            stat_rows.append({"Table": tbl, "Rows": "—"})
    st.table(pd.DataFrame(stat_rows))

    st.divider()

    # ── actions ───────────────────────────────────────────────────────────────
    col_a, col_b = st.columns(2)

    with col_a:
        st.subheader("🔄 Clear Reminder Sent")
        st.caption("Resets the reminder_sent table so reminders are re-sent for upcoming bookings.")
        if st.button("Clear reminder_sent", type="primary"):
            st.session_state["confirm_clear_reminders"] = True

        if st.session_state.get("confirm_clear_reminders"):
            st.warning("Clear ALL entries in reminder_sent?")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("✅ Confirm", key="clear_rem_yes"):
                    execute("DELETE FROM reminder_sent")
                    del st.session_state["confirm_clear_reminders"]
                    st.success("reminder_sent cleared.")
                    st.rerun()
            with c2:
                if st.button("Cancel", key="clear_rem_no"):
                    del st.session_state["confirm_clear_reminders"]
                    st.rerun()

    with col_b:
        st.subheader("💾 Export Database Backup")
        st.caption("Download a full SQL dump of the database.")
        if st.button("Generate SQL Backup"):
            if not db_path.exists():
                st.error("Database file not found.")
            else:
                with st.spinner("Generating backup…"):
                    buf = io.StringIO()
                    conn = sqlite3.connect(str(db_path))
                    for line in conn.iterdump():
                        buf.write(line + "\n")
                    conn.close()
                    backup_bytes = buf.getvalue().encode("utf-8")
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                st.download_button(
                    label="⬇️ Download backup.sql",
                    data=backup_bytes,
                    file_name=f"office_backup_{ts}.sql",
                    mime="text/plain",
                )

# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    require_auth()
    page = sidebar()

    if page == PAGES[0]:
        page_dashboard()
    elif page == PAGES[1]:
        page_users()
    elif page == PAGES[2]:
        page_bookings()
    elif page == PAGES[3]:
        page_clubs()
    elif page == PAGES[4]:
        page_events()
    elif page == PAGES[5]:
        page_broadcast()
    elif page == PAGES[6]:
        page_settings()


if __name__ == "__main__":
    main()
