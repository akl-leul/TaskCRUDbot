import logging
import os
import asyncio
import random
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder, 
    CommandHandler, 
    ContextTypes, 
    MessageHandler, 
    filters, 
    CallbackQueryHandler,
    ConversationHandler
)
from telegram.request import HTTPXRequest
from telegram_bot_calendar import DetailedTelegramCalendar
from dotenv import load_dotenv

import supabase_db as database
import scheduler
from flask import Flask
import threading

app_web = Flask(__name__)
main_bot = None
main_loop = None

@app_web.route('/')
def home():
    return "Bot is alive!", 200

@app_web.route('/cron')
def trigger_cron():
    if main_bot and main_loop:
        asyncio.run_coroutine_threadsafe(scheduler.run_all_checks(main_bot), main_loop)
        return "Cron executed", 200
    return "Bot not ready", 503

def run_flask():
    port = int(os.getenv("PORT", 8080))
    app_web.run(host='0.0.0.0', port=port)


# Load environment variables
load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Conversation States
DESCRIPTION, TIME, DATE = range(3)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_html(
        rf"Hi {user.mention_html()}! 🚀 I'm your *DailyTask Bot*."
        "\n\nI'll help you organize your tasks for tomorrow and beyond."
        "\n\n✨ *Commands:*"
        "\n/add - Add a new task step-by-step"
        "\n/list - View your tasks"
        "\n/delete - Remove a task"
        "\n/stop - Stop all notifications and clear your tasks"
        "\n/cancel - Cancel current action"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "🤖 *DailyTask Bot Help*\n\n"
        "✨ /add - Start the interactive task creation flow.\n"
        "📄 /list - Show all your upcoming tasks.\n"
        "❌ /delete - Choose tasks to remove.\n"
        "🛑 /stop - Clear ALL your tasks and stop notifications.\n"
        "🚫 /cancel - Stop adding a task anytime.\n\n"
        "💡 *Tips:* \n"
        "- I'll remind you 2 hours before the task starts.\n"
        "- You'll get a summary every morning at 8:00 AM."
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')

# --- Add Task Conversation ---

async def add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📝 *Step 1:* What is the task description?\n"
        "_(e.g., 'Finish the report' or 'Go to the gym')_",
        parse_mode='Markdown'
    )
    return DESCRIPTION

async def add_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['desc'] = update.message.text
    await update.message.reply_text(
        f"✅ Task: *{context.user_data['desc']}*\n\n"
        "⏰ *Step 2:* What time is it due? (Use HH:MM format)\n"
        "_(e.g., 09:00 or 15:30)_",
        parse_mode='Markdown'
    )
    return TIME

def parse_time(time_str: str):
    """Parses time strings in various formats (24h, 12h with AM/PM)."""
    formats = ["%H:%M", "%I:%M %p", "%I:%M%p", "%I%p", "%H:%M:%S"]
    time_str = time_str.strip().upper()
    for fmt in formats:
        try:
            dt = datetime.strptime(time_str, fmt)
            return dt.strftime("%H:%M")
        except ValueError:
            continue
    return None

async def add_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    time_str = update.message.text
    parsed_time = parse_time(time_str)
    
    if parsed_time:
        context.user_data['time'] = parsed_time
        
        # Start Calendar Selection
        calendar, step = DetailedTelegramCalendar().build()
        await update.message.reply_text(
            f"Select {step}:",
            reply_markup=calendar
        )
        return DATE
    else:
        await update.message.reply_text(
            "❌ *Invalid time format.*\n"
            "Please use forms like:\n"
            "• `14:30` (24h)\n"
            "• `02:30 PM` (12h)\n"
            "• `2pm` (Short 12h)",
            parse_mode='Markdown'
        )
        return TIME

async def add_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    result, key, step = DetailedTelegramCalendar().process(query.data)
    
    if not result and key:
        await query.edit_message_text(f"Select {step}:", reply_markup=key)
        return DATE
    elif result:
        due_date = result.strftime("%Y-%m-%d")
        desc = context.user_data['desc']
        due_time = context.user_data['time']
        
        database.add_task(query.from_user.id, desc, due_date, due_time)
        
        await query.edit_message_text(
            f"🎉 *Task Saved!*\n\n"
            f"📌 *What:* {desc}\n"
            f"📅 *When:* {due_date} at {due_time}\n"
            f"⏰ *Reminder:* 2 hours before.",
            parse_mode='Markdown'
        )
        context.user_data.clear()
        return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚫 Task creation cancelled.", 
        reply_markup=ReplyKeyboardRemove()
    )
    context.user_data.clear()
    return ConversationHandler.END

# --- Task Management ---

async def list_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    tasks = database.get_tasks(user_id)
    
    if not tasks:
        await update.message.reply_text(
            "🏝️ *Your plate is clean!*\n\n"
            "You have no upcoming tasks. Use /add to get started.",
            parse_mode='Markdown'
        )
        return
    
    # Date helper
    today = datetime.now().date()
    tomorrow = today + timedelta(days=1)
    now = datetime.now()
    
    # Grouping
    overdue_tasks = []
    today_tasks = []
    tomorrow_tasks = []
    upcoming_tasks = []
    
    for t in tasks:
        task_dt = datetime.strptime(f"{t[3]} {t[4]}", "%Y-%m-%d %H:%M")
        task_date = task_dt.date()
        
        if task_dt < now:
            overdue_tasks.append(t)
        elif task_date == today:
            today_tasks.append(t)
        elif task_date == tomorrow:
            tomorrow_tasks.append(t)
        elif task_date > tomorrow:
            upcoming_tasks.append(t)
            
    # Sort
    overdue_tasks.sort(key=lambda x: (x[3], x[4]))
    today_tasks.sort(key=lambda x: x[4])
    tomorrow_tasks.sort(key=lambda x: x[4])
    upcoming_tasks.sort(key=lambda x: (x[3], x[4]))
    
    display_name = update.effective_user.first_name
    message = f"📋 *{display_name}'s Task Overview*\n"
    message += "──────────────────\n\n"
    
    keyboard = []
    
    if overdue_tasks:
        message += "⚠️ *OVERDUE*\n"
        for t in overdue_tasks:
            message += f"  ◽️ `{t[3]}` {t[4]} — {t[2]}\n"
            keyboard.append([InlineKeyboardButton(f"Done ✅: {t[2]}", callback_data=f"del_{t[0]}")])
        message += "\n"

    if today_tasks:
        message += "🔴 *TODAY*\n"
        for t in today_tasks:
            message += f"  ⏳ `{t[4]}` — {t[2]}\n"
        message += "\n"
        
    if tomorrow_tasks:
        message += "🟡 *TOMORROW*\n"
        for t in tomorrow_tasks:
            message += f"  📅 `{t[4]}` — {t[2]}\n"
        message += "\n"
        
    if upcoming_tasks:
        message += "🔵 *UPCOMING*\n"
        for t in upcoming_tasks:
            message += f"  🗓️ `{t[3]}` at `{t[4]}`\n      _{t[2]}_\n"
        message += "\n"
        
    message += "──────────────────"
    
    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
    await update.message.reply_text(message, parse_mode='Markdown', reply_markup=reply_markup)

async def delete_tasks_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    tasks = database.get_tasks(user_id)
    
    if not tasks:
        await update.message.reply_text("Nothing to delete.")
        return
    
    keyboard = []
    for t in tasks:
        keyboard.append([InlineKeyboardButton(f"❌ {t[2]} ({t[3]})", callback_data=f"del_{t[0]}")])
        
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Select a task to delete:", reply_markup=reply_markup)

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    database.clear_user_tasks(user_id)
    await update.message.reply_text(
        "🛑 *Subscription Stopped.*\n\n"
        "I've cleared all your tasks and stopped all notifications. "
        "You can restart anytime by adding a task with /add or sending /start.",
        parse_mode='Markdown'
    )

MOTIVATIONS = [
    "🚀 *Legendary!* You're crushing it.",
    "✨ *Believe in yourself!* Every small step counts.",
    "🏆 *Success is near!* Keep that momentum going.",
    "🔥 *You're on fire!* There's no stopping you now.",
    "💪 *Strength and Honor!* Focus on the goal.",
    "🌟 *Shine on!* Your hard work is paying off.",
    "⚡ *Power move!* You've got this.",
    "🌈 *The sky is the limit!* Keep reaching higher."
]

async def generic_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    quote = random.choice(MOTIVATIONS)
    
    if query.data.startswith("del_"):
        task_id = int(query.data.split("_")[1])
        database.delete_task(task_id, query.from_user.id)
        await query.edit_message_text(text=f"✅ Task deleted successfully.\n\n{quote}", parse_mode='Markdown')
    elif query.data.startswith("start_y_"):
        task_id = int(query.data.split("_")[3])
        database.delete_task(task_id, query.from_user.id)
        await query.edit_message_text(text=f"🎉 *Awesome!* Task marked as started.\n\n{quote}", parse_mode='Markdown')
    elif query.data.startswith("start_n_"):
        await query.edit_message_text(text="No worries! I'll leave the task on your list. ✍️")
    elif query.data.startswith("cbcal"):
        # This is likely a calendar callback from an expired or cancelled session
        pass

def main():
    if not TOKEN or TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("Error: TELEGRAM_BOT_TOKEN not found in .env")
        return

    # database.init_db()  # Schema is managed in Supabase
    
    # Increase timeouts to handle potential network issues
    request = HTTPXRequest(connect_timeout=20, read_timeout=20)
    app = ApplicationBuilder().token(TOKEN).request(request).build()
    
    async def post_init(application):
        global main_bot, main_loop
        main_bot = application.bot
        main_loop = asyncio.get_running_loop()
        scheduler.start_scheduler(application.bot, main_loop)
        
        # Start Flask in a background thread
        threading.Thread(target=run_flask, daemon=True).start()

    app.post_init = post_init

    # Conversation Handler for adding tasks
    add_conv = ConversationHandler(
        entry_points=[CommandHandler("add", add_start)],
        states={
            DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_description)],
            TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_time)],
            DATE: [CallbackQueryHandler(add_date)]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(add_conv)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("list", list_tasks))
    app.add_handler(CommandHandler("delete", delete_tasks_menu))
    app.add_handler(CommandHandler("stop", stop_command))
    app.add_handler(CallbackQueryHandler(generic_callback)) # For legacy delete buttons

    print("Bot is starting...")
    app.run_polling(timeout=30)

if __name__ == '__main__':
    main()
