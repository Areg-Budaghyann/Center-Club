"""
Apply to database.py — add event_reminder_sent table and save_notification function.
Run: python3 db_migration_patch.py path/to/database.py
"""
import sys, ast

path = sys.argv[1] if len(sys.argv) > 1 else 'database.py'
content = open(path, encoding='utf-8').read()
changed = False

# 1. Add event_reminder_sent table
if 'event_reminder_sent' not in content:
    old = 'CREATE TABLE IF NOT EXISTS special_events'
    new = '''CREATE TABLE IF NOT EXISTS event_reminder_sent (
                event_id    INTEGER PRIMARY KEY,
                sent_at     TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS special_events'''
    content = content.replace(old, new)
    changed = True
    print('✓ Added event_reminder_sent table')

# 2. Add save_notification if missing
if 'def save_notification' not in content:
    notif_code = '''
def save_notification(user_id: int, chat_id: int, message_id: int) -> None:
    """Save a notification message ID to DB so admin panel can clear it."""
    try:
        with _connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO pending_notifications (user_id, chat_id, message_id) VALUES (?,?,?)",
                (user_id, chat_id, message_id)
            )
    except Exception:
        pass


'''
    # Insert before get_all_special_events or at end of file
    if 'def get_all_special_events' in content:
        content = content.replace('def get_all_special_events', notif_code + 'def get_all_special_events')
    else:
        content += notif_code
    changed = True
    print('✓ Added save_notification function')

# 3. Add pending_notifications table
if 'pending_notifications' not in content:
    old = 'CREATE TABLE IF NOT EXISTS event_reminder_sent'
    new = '''CREATE TABLE IF NOT EXISTS pending_notifications (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                chat_id     INTEGER NOT NULL,
                message_id  INTEGER NOT NULL,
                sent_at     TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS event_reminder_sent'''
    content = content.replace(old, new)
    changed = True
    print('✓ Added pending_notifications table')

if changed:
    ast.parse(content)
    open(path, 'w', encoding='utf-8').write(content)
    print(f'Saved: {path}')
else:
    print('No changes needed')
