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

def _clean_time(time_str):
    """Ensure time is in HH:MM format (strips seconds if present)."""
    if not time_str: return time_str
    parts = time_str.split(':')
    if len(parts) >= 2:
        return f"{parts[0].zfill(2)}:{parts[1].zfill(2)}"
    return time_str

# ─────────────────────────────────────────────
# USER REGISTRATION
# ─────────────────────────────────────────────

def register_user(user_id: int, username: str, first_name: str):
    """Upsert the user's profile. Called every time they send /start."""
    if not supabase: return
    supabase.table("users").upsert({
        "user_id": user_id,
        "username": username.lower().lstrip("@") if username else None,
        "first_name": first_name,
    }).execute()

def is_user_registered(user_id: int) -> bool:
    """Return True if the user has registered (sent /start at least once)."""
    if not supabase: return False
    response = supabase.table("users").select("user_id").eq("user_id", user_id).execute()
    return len(response.data) > 0

def get_user_by_username(username: str):
    """
    Find a registered user by their @username (case-insensitive, strips leading @).
    Returns the row dict or None.
    """
    if not supabase: return None
    clean = username.lower().lstrip("@")
    response = supabase.table("users").select("*").eq("username", clean).execute()
    return response.data[0] if response.data else None

# ─────────────────────────────────────────────
# TASK SHARING (COLLABORATIVE PLANNING)
# ─────────────────────────────────────────────

def share_task(task_id: int, owner_id: int, collaborator_id: int):
    """Share a task with another registered user. Ignores duplicate shares."""
    if not supabase: return
    supabase.table("shared_plans").upsert({
        "task_id": task_id,
        "owner_id": owner_id,
        "collaborator_id": collaborator_id,
    }).execute()

def get_shared_with_me(user_id: int):
    """
    Get tasks that other users have shared with me.
    Returns list of dicts with task + owner info.
    """
    if not supabase: return []
    response = (
        supabase.table("shared_plans")
        .select("id, task_id, tasks(description, due_date, due_time), owner_id, users!shared_plans_owner_id_fkey(first_name, username)")
        .eq("collaborator_id", user_id)
        .execute()
    )
    results = []
    for r in response.data:
        task = r.get("tasks") or {}
        owner = r.get("users") or {}
        results.append({
            "share_id": r["id"],
            "task_id": r["task_id"],
            "description": task.get("description", "Unknown Task"),
            "due_date": task.get("due_date", ""),
            "due_time": _clean_time(task.get("due_time", "")),
            "owner_first_name": owner.get("first_name", "Unknown"),
            "owner_username": owner.get("username", ""),
        })
    return results

def get_my_shares(owner_id: int):
    """
    Get tasks that I have shared with others.
    Returns list of dicts with task + collaborator info.
    """
    if not supabase: return []
    response = (
        supabase.table("shared_plans")
        .select("id, task_id, tasks(description, due_date, due_time), collaborator_id, users!shared_plans_collaborator_id_fkey(first_name, username)")
        .eq("owner_id", owner_id)
        .execute()
    )
    results = []
    for r in response.data:
        task = r.get("tasks") or {}
        collab = r.get("users") or {}
        results.append({
            "share_id": r["id"],
            "task_id": r["task_id"],
            "description": task.get("description", "Unknown Task"),
            "due_date": task.get("due_date", ""),
            "due_time": _clean_time(task.get("due_time", "")),
            "collab_first_name": collab.get("first_name", "Unknown"),
            "collab_username": collab.get("username", ""),
        })
    return results

def remove_share(share_id: int, owner_id: int):
    """Remove a share. The owner_id check prevents unauthorized removal."""
    if not supabase: return
    supabase.table("shared_plans").delete().eq("id", share_id).eq("owner_id", owner_id).execute()

# ─────────────────────────────────────────────
# EXISTING TASK FUNCTIONS
# ─────────────────────────────────────────────

def get_pending_checkins(date_str):
    if not supabase: return []
    response = supabase.table("tasks").select("*").eq("due_date", date_str).eq("notified_started", False).execute()
    return [
        (r['id'], r['user_id'], r['description'], r['due_date'], _clean_time(r['due_time']), r['reminder_minutes'], r['notified_morning'], r['notified_reminder'], r['notified_started'])
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
        (r['id'], r['user_id'], r['description'], r['due_date'], _clean_time(r['due_time']), r['reminder_minutes'], r['notified_morning'], r['notified_reminder'], r['notified_started'])
        for r in response.data
    ]

def get_users_to_notify_morning(date_str):
    if not supabase: return []
    response = supabase.table("tasks").select("user_id").eq("due_date", date_str).eq("notified_morning", False).execute()
    return list(set(r['user_id'] for r in response.data))

def get_tasks_for_reminders(date_str):
    if not supabase: return []
    response = supabase.table("tasks").select("*").eq("due_date", date_str).eq("notified_reminder", False).execute()
    return [
        (r['id'], r['user_id'], r['description'], r['due_date'], _clean_time(r['due_time']), r['reminder_minutes'], r['notified_morning'], r['notified_reminder'], r['notified_started'])
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
