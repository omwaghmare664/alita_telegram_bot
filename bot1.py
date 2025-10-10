from typing import Final
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import random
import json
import os

# --- Bot Config ---
TOKEN: Final = os.getenv("BOT_TOKEN")
BOT_USERNAME: Final = '@alitacode_bot'
ADMIN_ID: Final = 7327016053  # Replace with your Telegram user ID

# --- Persistent User Storage ---
USER_FILE = "user_ids.json"

def load_users():
    if os.path.exists(USER_FILE):
        with open(USER_FILE, "r") as file:
            return set(json.load(file))
    return set()

def save_users(users):
    with open(USER_FILE, "w") as file:
        json.dump(list(users), file)

# Dynamically track users
user_ids = load_users()

# --- Helper Functions ---
def get_coding_tip(language: str) -> str:
    tips = {
        "python": "Python tip: Use list comprehensions for concise and efficient loops.",
        "javascript": "JavaScript tip: Use '===' for strict equality checks to avoid type coercion.",
        "html": "HTML tip: Use semantic tags like <header>, <footer>, and <article> for better accessibility.",
        "css": "CSS tip: Use Flexbox for responsive layouts.",
        "java": "Java tip: Always close your resources using try-with-resources for better memory management."
    }
    return tips.get(language.lower(), "Sorry, I don't have a specific tip for that language yet.")

# --- Command Handlers ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    user_ids.add(chat_id)  # Add user to the list
    save_users(user_ids)  # Save to file
    welcome_message = (
        "Hey there! 👋\n"
        "I'm your advanced coding assistant bot! 🚀\n"
        "Use /help to see what I can do!"
    )
    await update.message.reply_text(welcome_message)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_message = (
        "Here are the commands you can use:\n"
        "/start - Start interacting with the bot.\n"
        "/help - Get a list of available commands.\n"
        "/suggest - Get coding suggestions (projects, tools, libraries).\n"
        "/tip [language] - Get a coding tip for a specific language.\n"
        "/joke - Hear a programming joke.\n"
        "/quote - Get a motivational coding quote.\n"
        "/tools - Learn about popular coding tools and frameworks.\n"
        "Admin-only: /adminpanel to send notifications."
    )
    await update.message.reply_text(help_message)

async def adminpanel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat_id != ADMIN_ID:
        await update.message.reply_text("Unauthorized access. This command is for the admin only.")
        return
    
    await update.message.reply_text(
        "Welcome to the Admin Panel. Use /send <message> to notify all users.\n"
        "Example: /send Hello, everyone!"
    )

async def send_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat_id != ADMIN_ID:
        await update.message.reply_text("Unauthorized access. This command is for the admin only.")
        return
    
    if not context.args:
        await update.message.reply_text("Please provide a message to send. Example: /send Hello!")
        return
    
    message = " ".join(context.args)
    failed = 0

    for user_id in user_ids:
        try:
            await context.bot.send_message(chat_id=user_id, text=message)
        except Exception as e:
            failed += 1

    await update.message.reply_text(
        f"Notification sent to {len(user_ids) - failed} users. Failed for {failed} users."
    )

# --- Other Commands ---
async def suggest_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    suggestions = [
        "Build a weather app using ReactJS and OpenWeather API.",
        "Learn Flask to create a lightweight Python web application.",
        "Explore Three.js for stunning 3D graphics in web projects.",
        "Try creating a Telegram bot using Python's `python-telegram-bot`!",
        "Create a personal finance tracker using MongoDB, Express, React, and Node (MERN stack)."
    ]
    suggestion = random.choice(suggestions)
    await update.message.reply_text(f"Here’s a suggestion for you:\n{suggestion}")

async def tip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        language = " ".join(context.args)
        response = get_coding_tip(language)
    else:
        response = "Please specify a language. Example: /tip python"
    await update.message.reply_text(response)

async def code_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text.lower()
    response = "I didn't understand that. Could you provide more details?"
    if "python" in user_message:
        response = "Python is a fantastic choice! Let me know if you need tips or snippets."
    elif "error" in user_message:
        response = "Can you describe the error? I'll help debug it."
    await update.message.reply_text(response)

async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("I didn't understand that command. Use /help to see what I can do!")

# --- Main Application ---
def main():
    app = Application.builder().token(TOKEN).build()

    # Command Handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("adminpanel", adminpanel_command))
    app.add_handler(CommandHandler("send", send_command))
    app.add_handler(CommandHandler("suggest", suggest_command))
    app.add_handler(CommandHandler("tip", tip_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, code_handler))
    app.add_handler(MessageHandler(filters.COMMAND, unknown_command))

    # Run the bot
    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()

