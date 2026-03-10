import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None

def init_db():
    # Schema is handled via migrations in Supabase
    pass

def get_pending_checkins(date_str):
    if not supabase: return []
    response = supabase.table("tasks").select("*").eq("due_date", date_str).eq("notified_started", False).execute()
    return [
        (r['id'], r['user_id'], r['description'], r['due_date'], r['due_time'], r['reminder_minutes'], r['notified_morning'], r['notified_reminder'], r['notified_started'])
        for r in response.data
    ]

def add_task(user_id, description, due_date, due_time, reminder_minutes=120):
    if not supabase: return
    supabase.table("tasks").insert({
        "user_id": user_id,
        "description": description,
        "due_date": due_date,
        "due_time": due_time,
        "reminder_minutes": reminder_minutes
    }).execute()

def get_tasks(user_id, date=None):
    if not supabase: return []
    query = supabase.table("tasks").select("*").eq("user_id", user_id)
    if date:
        query = query.eq("due_date", date)
    response = query.execute()
    return [
        (r['id'], r['user_id'], r['description'], r['due_date'], r['due_time'], r['reminder_minutes'], r['notified_morning'], r['notified_reminder'], r['notified_started'])
        for r in response.data
    ]

def delete_task(task_id, user_id):
    if not supabase: return
    supabase.table("tasks").delete().eq("id", task_id).eq("user_id", user_id).execute()

def update_task_notification(task_id, column):
    if not supabase: return
    supabase.table("tasks").update({column: True}).eq("id", task_id).execute()

def clear_user_tasks(user_id):
    if not supabase: return
    supabase.table("tasks").delete().eq("user_id", user_id).execute()
