import sqlite3
from datetime import datetime

DB_NAME = "tasks.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            description TEXT NOT NULL,
            due_date TEXT NOT NULL,
            due_time TEXT NOT NULL,
            reminder_minutes INTEGER DEFAULT 120,
            notified_morning INTEGER DEFAULT 0,
            notified_reminder INTEGER DEFAULT 0,
            notified_started INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()

def get_pending_checkins(date_str):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM tasks WHERE due_date = ? AND notified_started = 0', (date_str,))
    rows = cursor.fetchall()
    conn.close()
    return rows

def add_task(user_id, description, due_date, due_time, reminder_minutes=120):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO tasks (user_id, description, due_date, due_time, reminder_minutes)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, description, due_date, due_time, reminder_minutes))
    conn.commit()
    conn.close()

def get_tasks(user_id, date=None):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    if date:
        cursor.execute('SELECT * FROM tasks WHERE user_id = ? AND due_date = ?', (user_id, date))
    else:
        cursor.execute('SELECT * FROM tasks WHERE user_id = ?', (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return rows

def delete_task(task_id, user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM tasks WHERE id = ? AND user_id = ?', (task_id, user_id))
    conn.commit()
    conn.close()

def update_task_notification(task_id, column):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(f'UPDATE tasks SET {column} = 1 WHERE id = ?', (task_id,))
    conn.commit()
    conn.close()

def clear_user_tasks(user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM tasks WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Database initialized.")
