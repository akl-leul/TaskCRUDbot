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

import database
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

# Share Conversation States
SHARE_TASK_SELECT, SHARE_USERNAME_INPUT = range(3, 5)

# ─────────────────────────────────────────────────────────────────
# START & HELP
# ─────────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    # Auto-register user so others can find them by @username
    database.register_user(user.id, user.username or "", user.first_name or "")
    await update.message.reply_html(
        rf"Hi {user.mention_html()}! 🚀 I'm your <b>DailyTask Bot</b>."
        "\n\nI'll help you organize your tasks and <b>collaborate</b> with teammates."
        "\n\n✨ <b>Commands:</b>"
        "\n/add - Add a new task step-by-step"
        "\n/list - View your tasks"
        "\n/delete - Remove a task"
        "\n/share - Share a task with a teammate"
        "\n/shared - View tasks teammates shared with you"
        "\n/myshares - View tasks you've shared + unshare"
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
        "🤝 *Collaborative Planning:*\n"
        "/share - Share one of your tasks with a teammate by @username.\n"
        "/shared - See tasks that teammates have shared with you.\n"
        "/myshares - See tasks you've shared and remove shares.\n\n"
        "💡 *Tips:*\n"
        "- Teammates must have started the bot to be found by @username.\n"
        "- I'll remind you 2 hours before the task starts.\n"
        "- You'll get a summary every morning at 8:00 AM."
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')

# ─────────────────────────────────────────────────────────────────
# ADD TASK CONVERSATION
# ─────────────────────────────────────────────────────────────────

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
        "🚫 Action cancelled.", 
        reply_markup=ReplyKeyboardRemove()
    )
    context.user_data.clear()
    return ConversationHandler.END

# ─────────────────────────────────────────────────────────────────
# TASK MANAGEMENT (LIST / DELETE / STOP)
# ─────────────────────────────────────────────────────────────────

async def list_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows the initial menu for task management."""
    display_name = update.effective_user.first_name
    message = (
        f"📋 *Hello {display_name}!* 🚀\n"
        "How can I help you manage your tasks today?\n"
        "──────────────────"
    )
    
    keyboard = [
        [
            InlineKeyboardButton("📅 Today", callback_data="list_today"),
            InlineKeyboardButton("📅 Tomorrow", callback_data="list_tomorrow")
        ],
        [
            InlineKeyboardButton("📋 This Week", callback_data="list_week"),
            InlineKeyboardButton("🚨 Deadlines", callback_data="list_deadlines")
        ],
        [
            InlineKeyboardButton("🕒 Office Hours", callback_data="list_office")
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(message, parse_mode='Markdown', reply_markup=reply_markup)

async def handle_list_category(query, category):
    user_id = query.from_user.id
    tasks = database.get_tasks(user_id)
    
    if not tasks:
        await query.edit_message_text("🏝️ *Your plate is clean!* 🚀", parse_mode='Markdown')
        return

    today = datetime.now().date()
    tomorrow = today + timedelta(days=1)
    week_end = today + timedelta(days=7)
    now = datetime.now()
    
    filtered_tasks = []
    title = ""

    if category == "today":
        title = "🔴 *TODAY'S MISSIONS*"
        filtered_tasks = [t for t in tasks if datetime.strptime(f"{t[3]} {t[4]}", "%Y-%m-%d %H:%M").date() == today]
    elif category == "tomorrow":
        title = "🟠 *TOMORROW'S PLAN*"
        filtered_tasks = [t for t in tasks if datetime.strptime(f"{t[3]} {t[4]}", "%Y-%m-%d %H:%M").date() == tomorrow]
    elif category == "week":
        title = "📋 *THIS WEEK'S GOALS*"
        filtered_tasks = [t for t in tasks if today <= datetime.strptime(f"{t[3]} {t[4]}", "%Y-%m-%d %H:%M").date() <= week_end]
    elif category == "deadlines":
        title = "🚨 *DEADLINES & OVERDUE*"
        filtered_tasks = [t for t in tasks if datetime.strptime(f"{t[3]} {t[4]}", "%Y-%m-%d %H:%M") < now]
    elif category == "office":
        await query.edit_message_text(
            "🕒 *Office Hours*\n\n"
            "Academic Team is available:\n"
            "• Mon - Fri: 9:00 AM - 5:00 PM\n"
            "• Sat: 10:00 AM - 1:00 PM\n\n"
            "_(Use /add to schedule a meeting)_", 
            parse_mode='Markdown'
        )
        return

    if not filtered_tasks:
        await query.edit_message_text(f"{title}\n\nNo tasks found here! ✨", parse_mode='Markdown')
        return

    filtered_tasks.sort(key=lambda x: (x[3], x[4]))
    message = f"{title}\n──────────────────\n\n"
    
    keyboard = []
    for t in filtered_tasks:
        message += f"◽️ `{t[3]}` {t[4]} — *{t[2]}*\n"
        keyboard.append([InlineKeyboardButton(f"Done ✅: {t[2]}", callback_data=f"del_{t[0]}")])
    
    keyboard.append([InlineKeyboardButton("⬅️ Back to Menu", callback_data="list_back")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(message, parse_mode='Markdown', reply_markup=reply_markup)

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

# ─────────────────────────────────────────────────────────────────
# COLLABORATIVE PLANNING: /share
# ─────────────────────────────────────────────────────────────────

async def share_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Entry point for /share — show user's tasks to pick from."""
    user_id = update.effective_user.id
    tasks = database.get_tasks(user_id)

    if not tasks:
        await update.message.reply_text(
            "📭 You have no tasks to share yet.\n"
            "Add one first with /add!"
        )
        return ConversationHandler.END

    keyboard = []
    for t in tasks:
        label = f"📌 {t[2][:30]} — {t[3]}"
        keyboard.append([InlineKeyboardButton(label, callback_data=f"sharetask_{t[0]}")])
    keyboard.append([InlineKeyboardButton("🚫 Cancel", callback_data="sharetask_cancel")])

    await update.message.reply_text(
        "🤝 *Share a Task*\n\nPick the task you want to share:",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return SHARE_TASK_SELECT

async def share_task_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User picked a task. Now ask for the collaborator's @username."""
    query = update.callback_query
    await query.answer()

    if query.data == "sharetask_cancel":
        await query.edit_message_text("🚫 Share cancelled.")
        context.user_data.clear()
        return ConversationHandler.END

    task_id = int(query.data.split("_")[1])
    context.user_data['share_task_id'] = task_id

    await query.edit_message_text(
        "👤 *Who do you want to share with?*\n\n"
        "Enter their Telegram @username:\n_(e.g., @john_doe)_",
        parse_mode='Markdown'
    )
    return SHARE_USERNAME_INPUT

async def share_username_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Received @username — look up user and create the share."""
    username_input = update.message.text.strip()
    task_id = context.user_data.get('share_task_id')
    owner_id = update.effective_user.id

    # Look up collaborator
    collab = database.get_user_by_username(username_input)

    if not collab:
        await update.message.reply_text(
            f"❌ *@{username_input.lstrip('@')} is not registered.*\n\n"
            "They need to send /start to this bot first before you can share tasks with them.",
            parse_mode='Markdown'
        )
        context.user_data.clear()
        return ConversationHandler.END

    collab_id = collab['user_id']

    if collab_id == owner_id:
        await update.message.reply_text("😅 You can't share a task with yourself!")
        context.user_data.clear()
        return ConversationHandler.END

    # Create the share
    database.share_task(task_id, owner_id, collab_id)

    # Get task details for the notification
    tasks = database.get_tasks(owner_id)
    task_info = next((t for t in tasks if t[0] == task_id), None)
    task_desc = task_info[2] if task_info else "a task"
    owner_name = update.effective_user.first_name

    await update.message.reply_text(
        f"✅ *Task shared successfully!*\n\n"
        f"📌 *{task_desc}*\n"
        f"👤 Shared with: @{collab['username']}",
        parse_mode='Markdown'
    )

    # Notify the collaborator
    try:
        await context.bot.send_message(
            chat_id=collab_id,
            text=(
                f"🤝 *{owner_name} shared a task with you!*\n\n"
                f"📌 *{task_desc}*\n"
                f"📅 {task_info[3] if task_info else ''} at {task_info[4] if task_info else ''}\n\n"
                f"Use /shared to view all tasks shared with you."
            ),
            parse_mode='Markdown'
        )
    except Exception:
        pass  # Collaborator may have blocked the bot; that's okay

    context.user_data.clear()
    return ConversationHandler.END

# ─────────────────────────────────────────────────────────────────
# COLLABORATIVE PLANNING: /shared and /myshares
# ─────────────────────────────────────────────────────────────────

async def shared_with_me(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show tasks other users have shared with me."""
    user_id = update.effective_user.id
    shares = database.get_shared_with_me(user_id)

    if not shares:
        await update.message.reply_text(
            "📭 *No shared tasks yet.*\n\n"
            "When a teammate shares a task with you, it will appear here.",
            parse_mode='Markdown'
        )
        return

    message = "🤝 *Tasks Shared With You*\n──────────────────\n\n"
    for s in shares:
        owner_tag = f"@{s['owner_username']}" if s['owner_username'] else s['owner_first_name']
        message += (
            f"📌 *{s['description']}*\n"
            f"   📅 {s['due_date']} at {s['due_time']}\n"
            f"   👤 From: {owner_tag}\n\n"
        )

    await update.message.reply_text(message, parse_mode='Markdown')

async def my_shares(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show tasks I've shared with others, with an Unshare button."""
    user_id = update.effective_user.id
    shares = database.get_my_shares(user_id)

    if not shares:
        await update.message.reply_text(
            "📭 *You haven't shared any tasks yet.*\n\n"
            "Use /share to collaborate with a teammate.",
            parse_mode='Markdown'
        )
        return

    message = "📤 *Tasks You've Shared*\n──────────────────\n\n"
    keyboard = []
    for s in shares:
        collab_tag = f"@{s['collab_username']}" if s['collab_username'] else s['collab_first_name']
        message += (
            f"📌 *{s['description']}*\n"
            f"   📅 {s['due_date']} at {s['due_time']}\n"
            f"   👤 With: {collab_tag}\n\n"
        )
        keyboard.append([InlineKeyboardButton(
            f"❌ Unshare: {s['description'][:25]} → {collab_tag}",
            callback_data=f"unshare_{s['share_id']}"
        )])

    await update.message.reply_text(
        message,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ─────────────────────────────────────────────────────────────────
# CALLBACK QUERY ROUTER
# ─────────────────────────────────────────────────────────────────

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
    elif query.data.startswith("unshare_"):
        share_id = int(query.data.split("_")[1])
        database.remove_share(share_id, query.from_user.id)
        await query.edit_message_text(
            text="✅ *Share removed successfully.*\n\nThe collaborator can no longer see this task in /shared.",
            parse_mode='Markdown'
        )
    elif query.data.startswith("list_"):
        category = query.data.split("_")[1]
        if category == "back":
            display_name = query.from_user.first_name
            message = (
                f"📋 *Hello {display_name}!* 🚀\n"
                "How can I help you manage your tasks today?\n"
                "──────────────────"
            )
            keyboard = [
                [InlineKeyboardButton("📅 Today", callback_data="list_today"), InlineKeyboardButton("📅 Tomorrow", callback_data="list_tomorrow")],
                [InlineKeyboardButton("📋 This Week", callback_data="list_week"), InlineKeyboardButton("🚨 Deadlines", callback_data="list_deadlines")],
                [InlineKeyboardButton("🕒 Office Hours", callback_data="list_office")]
            ]
            await query.edit_message_text(message, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await handle_list_category(query, category)
    elif query.data.startswith("cbcal"):
        pass

# ─────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────

def main():
    if not TOKEN or TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("Error: TELEGRAM_BOT_TOKEN not found in .env")
        return

    request = HTTPXRequest(connect_timeout=20, read_timeout=20)
    app = ApplicationBuilder().token(TOKEN).request(request).build()
    
    async def post_init(application):
        global main_bot, main_loop
        main_bot = application.bot
        main_loop = asyncio.get_running_loop()
        scheduler.start_scheduler(application.bot, main_loop)
        threading.Thread(target=run_flask, daemon=True).start()

    app.post_init = post_init

    # Conversation Handler: Add Task
    add_conv = ConversationHandler(
        entry_points=[CommandHandler("add", add_start)],
        states={
            DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_description)],
            TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_time)],
            DATE: [CallbackQueryHandler(add_date, pattern="^cbcal")],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Conversation Handler: Share Task
    share_conv = ConversationHandler(
        entry_points=[CommandHandler("share", share_start)],
        states={
            SHARE_TASK_SELECT: [CallbackQueryHandler(share_task_selected, pattern="^sharetask_")],
            SHARE_USERNAME_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, share_username_received)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(add_conv)
    app.add_handler(share_conv)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("list", list_tasks))
    app.add_handler(CommandHandler("delete", delete_tasks_menu))
    app.add_handler(CommandHandler("stop", stop_command))
    app.add_handler(CommandHandler("shared", shared_with_me))
    app.add_handler(CommandHandler("myshares", my_shares))
    app.add_handler(CallbackQueryHandler(generic_callback))

    print("Bot is starting...")
    app.run_polling(timeout=30)

if __name__ == '__main__':
    main()
