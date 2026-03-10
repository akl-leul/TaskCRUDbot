from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
import database
import asyncio
from telegram import Bot
import os
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

async def send_morning_notifications(bot: Bot):
    today_dt = datetime.now()
    today_str = today_dt.strftime("%Y-%m-%d")
    
    users = database.get_users_to_notify_morning(today_str)
    
    for user_id in users:
        tasks = database.get_tasks(user_id, today_str)
        if tasks:
            message = (
                "✨ *Daily Briefing* ✨\n"
                "──────────────────\n"
                "☀️ *Good Morning!*\n"
                "Here are your challenges for today:\n\n"
            )
            for t in tasks:
                message += f"◽️ `{t[4]}` — *{t[2]}*\n"
            
            message += "\n🚀 *Go get 'em!*"
            
            await bot.send_message(chat_id=user_id, text=message, parse_mode='Markdown')
            for t in tasks:
                database.update_task_notification(t[0], "notified_morning")

async def check_reminders(bot: Bot):
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    
    tasks = database.get_tasks_for_reminders(today)
    
    for t in tasks:
        task_id, user_id, desc, _, due_time, reminder_min, _, _, _ = t
        due_datetime = datetime.strptime(f"{today} {due_time}", "%Y-%m-%d %H:%M")
        
        if now >= (due_datetime - timedelta(minutes=reminder_min)):
            await bot.send_message(chat_id=user_id, text=f"⏰ *Reminder*: {desc} is due at {due_time}!")
            database.update_task_notification(task_id, "notified_reminder")

async def check_post_tasks(bot: Bot):
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    
    tasks = database.get_pending_checkins(today)
    
    for t in tasks:
        task_id, user_id, desc, _, due_time, _, _, _, _ = t
        due_datetime = datetime.strptime(f"{today} {due_time}", "%Y-%m-%d %H:%M")
        
        # Check if 2 minutes have passed since due_time
        if now >= (due_datetime + timedelta(minutes=2)):
            keyboard = [
                [
                    InlineKeyboardButton("✅ Yes, started!", callback_data=f"start_y_{task_id}"),
                    InlineKeyboardButton("❌ Not yet", callback_data=f"start_n_{task_id}")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await bot.send_message(
                chat_id=user_id, 
                text=f"⏰ *Check-in*: Have you started \"{desc}\"?\n_(It's been 2 minutes since your scheduled time)_",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            database.update_task_notification(task_id, "notified_started")

async def run_all_checks(bot: Bot):
    """Run all scheduled checks immediately (used for external cron triggers)."""
    await send_morning_notifications(bot)
    await check_reminders(bot)
    await check_post_tasks(bot)

def start_scheduler(bot: Bot, loop):
    scheduler = BackgroundScheduler()
    
    # Morning notification at 8:00 AM
    scheduler.add_job(lambda: asyncio.run_coroutine_threadsafe(send_morning_notifications(bot), loop), 
                      'cron', hour=8, minute=0)
    
    # Check reminders and post-task check-ins every minute
    scheduler.add_job(lambda: asyncio.run_coroutine_threadsafe(check_reminders(bot), loop), 
                      'interval', minutes=1)
    scheduler.add_job(lambda: asyncio.run_coroutine_threadsafe(check_post_tasks(bot), loop), 
                      'interval', minutes=1)
    
    scheduler.start()
