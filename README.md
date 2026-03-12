# DailyTask Bot Setup Guide

**Created by Leul**

DailyTask Bot is a powerful, simple-to-use Telegram bot designed to help you manage your daily to-dos, avoid missing important deadlines, and collaborate with others. Get morning summaries, timely reminders, and easily share tasks with friends or teammates—all from your Telegram app!

---

## Table of Contents

- [Features](#features)
- [Getting Started](#getting-started)
- [Bot Commands](#bot-commands)
- [Usage Examples](#usage-examples)
- [Support & Feedback](#support--feedback)
- [Contributing](#contributing)
- [License](#license)

---

## Features

- **Automatic Morning Summary**: Receive a daily overview of all your tasks at 8:00 AM.
- **Smart Reminders**: The bot reminds you 2 hours before every task is due.
- **Task Collaboration**: Share tasks easily with friends or teammates and track both incoming and outgoing shared tasks.
- **Rich Command Set**: Includes task creation, editing, deletion, sharing, and organized listing.
- **Telegram-native**: All interactions take place right from your Telegram app.
- **Easy Setup**: Just enter your token and run with Python—no servers or complex deployment needed.

---

## Getting Started

### 1. **Pre-requisites**

- Python 3.10+ installed on your system
- A Telegram account

### 2. **Get a Telegram Bot Token**

- Message [@BotFather](https://t.me/BotFather) on Telegram.
- Use the `/newbot` command to create a new bot.
- Note and copy the API Token provided.

### 3. **Configure Your Environment**

- Clone or download this repository.
- At the root directory, open the `.env` file (create it if it doesn't exist).
- Paste your Telegram bot token as follows:

  ```
  BOT_TOKEN=YOUR_BOT_TOKEN_HERE
  ```

### 4. **Install Dependencies**

Open a terminal in your project folder and execute:

```bash
pip install python-telegram-bot apscheduler python-dotenv
```

### 5. **Run the Bot**

```bash
python bot.py
```

The bot will start running and respond to messages sent to your Telegram bot.

---

## Bot Commands

- `/start` — Initialize the bot and get a welcome message.
- `/add <description> <HH:MM> [YYYY-MM-DD]` — Add a new task. (Date defaults to tomorrow if not specified)
- `/edit <task_id> <new_description> [HH:MM] [YYYY-MM-DD]` — Edit an existing task.
- `/list` — View all your current scheduled tasks.
- `/delete` — Select and delete tasks via interactive buttons.
- `/share <task_id> <@username>` — Share a specific task with another Telegram user.
- `/shared` — View tasks shared with you by others.
- `/myshare` — View tasks you have shared with other users.
- `/help` — Show this help message and available commands.

---

## Usage Examples

**Add a Task:**
```
/add Submit report 14:00 2026-03-15
```
(Add a task titled "Submit report" for 2:00 PM, March 15th.)

**Edit a Task:**
```
/edit 3 Finish draft 16:00
```
(Edits task with ID 3, updates description and sets time to 4:00 PM. Date remains unchanged.)

**Share a Task:**
```
/share 5 @friendusername
```
(Shares your task with ID 5 to a friend.)

---

## Support & Feedback

- For issues, bug reports, or feature requests, open an [issue here](https://github.com/akl-leul/TaskCRUDbot/issues).
- You’re welcome to contribute—just fork the repo and make a pull request!
- Feel free to contact the creator [on Telegram](https://t.me/Leul_et) for support.

---

## Contributing

Want to improve this bot? Contributions are welcome! Please open an issue to discuss your ideas or submit a pull request directly.

---

## License

This project is open-sourced under the MIT License. See [LICENSE](LICENSE) for details.

---

**Created with ❤️ by Leul**
