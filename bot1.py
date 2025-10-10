from typing import Final
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import random
import json
import os
import logging

# --- Logging ---
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# --- Bot Config ---
TOKEN: Final = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise ValueError("BOT_TOKEN environment variable not set!")

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
    chat_id = update.effective_chat.id
    user_ids.add(chat_id)
    save_users(user_ids)
    welcome_message = (
        "Hey there! 👋\n"
        "I'm your advanced coding assistant bot! 🚀\n"
        "Use /help to see what I can do!"
    )
    await update.message.reply_text(welcome_message)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_message = (
        "Commands:\n"
        "/start - Start interacting with the bot.\n"
        "/help - Show this help message.\n"
        "/suggest - Get coding suggestions.\n"
        "/tip [language] - Get a coding tip.\n"
        "/joke - Hear a programming joke.\n"
        "/quote - Get a motivational coding quote.\n"
        "/tools - Learn about coding tools.\n"
        "Admin-only: /adminpanel to send notifications."
    )
    await update.message.reply_text(help_message)

async def adminpanel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ADMIN_ID:
        await update.message.reply_text("Unauthorized access. Admin only.")
        return
    await update.message.reply_text(
        "Admin Panel:\nUse /send <message> to notify all users."
    )

async def send_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ADMIN_ID:
        await update.message.reply_text("Unauthorized access. Admin only.")
        return
    if not context.args:
        await update.message.reply_text("Provide a message. Example: /send Hello!")
        return
    message = " ".join(context.args)
    failed = 0
    for user_id in user_ids:
        try:
            await context.bot.send_message(chat_id=user_id, text=message)
        except Exception as e:
            failed += 1
    await update.message.reply_text(
        f"Sent to {len(user_ids)-failed} users. Failed for {failed}."
    )

async def suggest_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    suggestions = [
        "Build a weather app using ReactJS and OpenWeather API.",
        "Learn Flask to create a lightweight Python web application.",
        "Explore Three.js for 3D graphics in web projects.",
        "Try creating a Telegram bot using python-telegram-bot!",
        "Create a personal finance tracker using the MERN stack."
    ]
    suggestion = random.choice(suggestions)
    await update.message.reply_text(f"Suggestion:\n{suggestion}")

async def tip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        language = " ".join(context.args)
        response = get_coding_tip(language)
    else:
        response = "Specify a language. Example: /tip python"
    await update.message.reply_text(response)

async def code_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text.lower()
    response = "I didn't understand that. Provide more details."
    if "python" in user_message:
        response = "Python is great! Ask for tips or snippets."
    elif "error" in user_message:
        response = "Describe the error, I can help debug."
    await update.message.reply_text(response)

async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Unknown command. Use /help for commands.")

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
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.BOT, code_handler))
    app.add_handler(MessageHandler(filters.COMMAND, unknown_command))

    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
