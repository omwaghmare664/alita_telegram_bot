from typing import Final, Dict, List
from telegram import (
    Update, 
    InlineKeyboardButton, 
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
    BotCommand
)
from telegram.ext import (
    Application, 
    CommandHandler, 
    MessageHandler, 
    CallbackQueryHandler,
    ContextTypes,
    filters
)
import random
import json
import os
import logging
import asyncio
from datetime import datetime, timedelta
import aiohttp
import signal
import sys

# --- Enhanced Logging ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Bot Config ---
TOKEN: Final = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise ValueError("BOT_TOKEN environment variable not set!")

BOT_USERNAME: Final = '@alitacode_bot'
ADMIN_ID: Final = 7327016053  # Your Telegram user ID

# --- Webhook Configuration for Production ---
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")
PORT = int(os.getenv("PORT", 8443))

# --- Persistent Storage ---
USER_FILE = "user_data.json"
GROUP_FILE = "group_data.json"
SETTINGS_FILE = "bot_settings.json"

class DataManager:
    @staticmethod
    def load_data(filename, default=None):
        if default is None:
            default = {}
        try:
            if os.path.exists(filename):
                with open(filename, "r") as file:
                    return json.load(file)
        except Exception as e:
            logger.error(f"Error loading {filename}: {e}")
        return default

    @staticmethod
    def save_data(filename, data):
        try:
            with open(filename, "w") as file:
                json.dump(data, file, indent=2)
        except Exception as e:
            logger.error(f"Error saving {filename}: {e}")

# Initialize data
user_data = DataManager.load_data(USER_FILE, {})
group_data = DataManager.load_data(GROUP_FILE, {})
bot_settings = DataManager.load_data(SETTINGS_FILE, {
    "auto_reply": True,
    "welcome_message": True,
    "anti_spam": True,
    "daily_updates": False
})

# --- API Services ---
class APIServices:
    @staticmethod
    async def get_weather(city: str = "London") -> str:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"http://wttr.in/{city}?format=3") as response:
                    if response.status == 200:
                        return await response.text()
        except Exception as e:
            logger.error(f"Weather API error: {e}")
            return f"🌤️ Weather for {city}: Service unavailable"

    @staticmethod
    async def get_joke() -> str:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("https://v2.jokeapi.dev/joke/Programming?type=single", timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get('joke', 'Why do programmers prefer dark mode? Because light attracts bugs!')
        except Exception as e:
            logger.error(f"Joke API error: {e}")
            return "😂 Why do programmers prefer dark mode? Because light attracts bugs!"

    @staticmethod
    async def get_news() -> str:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("https://api.currentsapi.services/v1/latest-news?apiKey=demo", timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        articles = data.get('news', [])[:3]
                        news = "📰 *Latest News:*\n\n"
                        for article in articles:
                            title = article.get('title', 'No title')
                            news += f"• {title}\n"
                        return news
        except Exception as e:
            logger.error(f"News API error: {e}")
            return "📰 Stay tuned for the latest updates!"

    @staticmethod
    async def get_crypto_price(coin: str = "bitcoin") -> str:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"https://api.coingecko.com/api/v3/simple/price?ids={coin}&vs_currencies=usd", timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        price = data.get(coin, {}).get('usd', 'N/A')
                        return f"💰 *{coin.title()}*: `${price}`"
        except Exception as e:
            logger.error(f"Crypto API error: {e}")
            return "💰 Crypto data currently unavailable"

# --- Keyboard Layouts ---
class Keyboards:
    @staticmethod
    def main_menu():
        return ReplyKeyboardMarkup([
            [KeyboardButton("🚀 Quick Tools"), KeyboardButton("📊 Live Updates")],
            [KeyboardButton("🎮 Entertainment"), KeyboardButton("⚙️ Settings")],
            [KeyboardButton("👨‍💻 Admin Panel")]
        ], resize_keyboard=True, input_field_placeholder="Choose an option...")

    @staticmethod
    def quick_tools():
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("🌤️ Weather", callback_data="weather"),
             InlineKeyboardButton("💰 Crypto", callback_data="crypto")],
            [InlineKeyboardButton("📰 News", callback_data="news"),
             InlineKeyboardButton("⏰ Time", callback_data="time")],
            [InlineKeyboardButton("🔙 Main Menu", callback_data="back_main")]
        ])

    @staticmethod
    def entertainment():
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("😂 Joke", callback_data="joke"),
             InlineKeyboardButton("🎲 Random Fact", callback_data="fact")],
            [InlineKeyboardButton("🤔 Advice", callback_data="advice"),
             InlineKeyboardButton("📚 Quote", callback_data="quote")],
            [InlineKeyboardButton("🔙 Main Menu", callback_data="back_main")]
        ])

    @staticmethod
    def admin_panel():
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 Broadcast", callback_data="broadcast"),
             InlineKeyboardButton("📊 Stats", callback_data="stats")],
            [InlineKeyboardButton("👥 Users", callback_data="users"),
             InlineKeyboardButton("⚙️ Settings", callback_data="bot_settings")],
            [InlineKeyboardButton("🔄 Restart", callback_data="restart"),
             InlineKeyboardButton("📋 Logs", callback_data="logs")],
            [InlineKeyboardButton("🔙 Main Menu", callback_data="back_main")]
        ])

    @staticmethod
    def back_only():
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Main Menu", callback_data="back_main")]
        ])

# --- Message Templates ---
class Messages:
    WELCOME = """
🤖 *Welcome to Advanced Assistant Bot* 🚀

*Quick Access Features:*
✨ Weather Updates • Crypto Prices • News
🎮 Jokes • Facts • Quotes • Advice
📊 Live Data • Group Management
⚙️ Smart Settings • Admin Tools

Use the menu below or type /help for guidance!
"""

    HELP = """
📖 *Available Commands:*

/main - Show main menu
/help - Show this help message
/admin - Admin panel (Admin only)
/status - Check bot status

🛠️ *Group Features:*
• Auto welcome messages
• Smart replies
• Live updates
• Entertainment

*Need assistance?* Contact the admin!
"""

# --- Core Handlers ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    
    # Initialize user data
    if user_id not in user_data:
        user_data[user_id] = {
            "first_seen": datetime.now().isoformat(),
            "usage_count": 0,
            "username": update.effective_user.username,
            "first_name": update.effective_user.first_name
        }
    
    user_data[user_id]["usage_count"] += 1
    user_data[user_id]["last_seen"] = datetime.now().isoformat()
    DataManager.save_data(USER_FILE, user_data)
    
    await update.message.reply_text(
        Messages.WELCOME,
        reply_markup=Keyboards.main_menu(),
        parse_mode='Markdown'
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        Messages.HELP,
        parse_mode='Markdown'
    )

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_count = len(user_data)
    group_count = len(group_data)
    
    status_text = f"""
🤖 *Bot Status*

✅ *Operational*
👥 Users: {user_count}
💬 Groups: {group_count}
🕐 Uptime: Active
🔧 Version: 2.0 Professional

All systems normal! 🚀
"""
    await update.message.reply_text(status_text, parse_mode='Markdown')

# --- Button Handlers ---
async def handle_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    
    if text == "🚀 Quick Tools":
        await update.message.reply_text(
            "🛠️ *Quick Tools* - Select a service:",
            reply_markup=Keyboards.quick_tools(),
            parse_mode='Markdown'
        )
    
    elif text == "🎮 Entertainment":
        await update.message.reply_text(
            "🎮 *Entertainment* - Choose fun activity:",
            reply_markup=Keyboards.entertainment(),
            parse_mode='Markdown'
        )
    
    elif text == "👨‍💻 Admin Panel":
        if update.effective_user.id != ADMIN_ID:
            await update.message.reply_text("❌ Admin access required!")
            return
        
        user_count = len(user_data)
        group_count = len(group_data)
        
        admin_text = f"""
👨‍💻 *Admin Panel*

📊 *Statistics:*
• Users: {user_count}
• Groups: {group_count}
• Active: ✅

🔧 *Management Tools:*
• Broadcast messages
• User management
• System settings
"""
        await update.message.reply_text(
            admin_text,
            reply_markup=Keyboards.admin_panel(),
            parse_mode='Markdown'
        )
    
    elif text == "⚙️ Settings":
        settings_text = """
⚙️ *Bot Settings*

*Current Configuration:*
• Auto Reply: ✅
• Welcome Messages: ✅  
• Anti-Spam: ✅
• Daily Updates: ❌

Use admin panel to modify settings.
"""
        await update.message.reply_text(settings_text, parse_mode='Markdown')
    
    elif text == "📊 Live Updates":
        # Provide quick live updates
        weather = await APIServices.get_weather()
        crypto = await APIServices.get_crypto_price()
        
        update_text = f"""
📊 *Live Updates*

{weather}
{crypto}

*More tools available in Quick Tools!*
"""
        await update.message.reply_text(update_text, parse_mode='Markdown')

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    try:
        if data == "weather":
            weather = await APIServices.get_weather()
            await query.edit_message_text(
                f"🌤️ *Weather Update:*\n{weather}",
                reply_markup=Keyboards.back_only(),
                parse_mode='Markdown'
            )
        
        elif data == "crypto":
            crypto = await APIServices.get_crypto_price()
            await query.edit_message_text(
                crypto,
                reply_markup=Keyboards.back_only(),
                parse_mode='Markdown'
            )
        
        elif data == "news":
            news = await APIServices.get_news()
            await query.edit_message_text(
                news,
                reply_markup=Keyboards.back_only(),
                parse_mode='Markdown'
            )
        
        elif data == "time":
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
            await query.edit_message_text(
                f"🕐 *Current Time:*\n`{current_time}`",
                reply_markup=Keyboards.back_only(),
                parse_mode='Markdown'
            )
        
        elif data == "joke":
            joke = await APIServices.get_joke()
            await query.edit_message_text(
                f"😂 *Programming Joke:*\n{joke}",
                reply_markup=Keyboards.back_only(),
                parse_mode='Markdown'
            )
        
        elif data == "fact":
            facts = [
                "The first computer bug was an actual moth found in Harvard's Mark II computer in 1947.",
                "Python is named after Monty Python, not the snake.",
                "There are over 700 programming languages in the world.",
                "The first computer virus was created in 1983.",
                "JavaScript was written in just 10 days in 1995."
            ]
            await query.edit_message_text(
                f"📚 *Random Fact:*\n{random.choice(facts)}",
                reply_markup=Keyboards.back_only(),
                parse_mode='Markdown'
            )
        
        elif data == "stats":
            if update.effective_user.id != ADMIN_ID:
                await query.edit_message_text("❌ Admin access required!")
                return
            
            user_count = len(user_data)
            group_count = len(group_data)
            active_users = len([u for u in user_data.values() if datetime.fromisoformat(u.get('last_seen', datetime.now().isoformat())) > datetime.now() - timedelta(days=1)])
            
            stats_text = f"""
📊 *Detailed Statistics*

👥 *Users:*
• Total: {user_count}
• Active (24h): {active_users}
• New today: Calculating...

💬 *Groups:*
• Total: {group_count}

⚙️ *System:*
• Uptime: Active
• Memory: Optimized
• Performance: ✅
"""
            await query.edit_message_text(stats_text, parse_mode='Markdown')
        
        elif data == "back_main":
            await query.edit_message_text(
                "🏠 *Main Menu* - Choose an option:",
                reply_markup=Keyboards.main_menu(),
                parse_mode='Markdown'
            )
        
        else:
            await query.edit_message_text(
                "🛠️ *Feature in development* 🔧",
                reply_markup=Keyboards.back_only(),
                parse_mode='Markdown'
            )
    
    except Exception as e:
        logger.error(f"Button handler error: {e}")
        await query.edit_message_text(
            "❌ Service temporarily unavailable. Please try again.",
            reply_markup=Keyboards.back_only()
        )

# --- Message Handler ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message is None:
        return
        
    user_id = str(update.effective_user.id)
    text = update.message.text
    
    # Initialize user data if not exists
    if user_id not in user_data:
        user_data[user_id] = {
            "first_seen": datetime.now().isoformat(),
            "usage_count": 0,
            "username": update.effective_user.username,
            "first_name": update.effective_user.first_name
        }
    
    user_data[user_id]["usage_count"] += 1
    user_data[user_id]["last_seen"] = datetime.now().isoformat()
    
    # Smart replies for common messages
    if any(word in text.lower() for word in ['hello', 'hi', 'hey', 'hola']):
        await update.message.reply_text("👋 Hello! How can I assist you today?")
    
    elif any(word in text.lower() for word in ['thank', 'thanks', 'thank you']):
        await update.message.reply_text("😊 You're welcome! Need anything else?")
    
    elif any(word in text.lower() for word in ['how are you', 'how are you doing']):
        await update.message.reply_text("🤖 I'm running perfectly! Ready to help you.")
    
    elif any(word in text.lower() for word in ['bye', 'goodbye', 'see you']):
        await update.message.reply_text("👋 Goodbye! Feel free to come back anytime!")
    
    elif any(word in text.lower() for word in ['weather', 'temperature', 'forecast']):
        weather = await APIServices.get_weather()
        await update.message.reply_text(f"🌤️ {weather}")
    
    elif any(word in text.lower() for word in ['bitcoin', 'crypto', 'price']):
        crypto = await APIServices.get_crypto_price()
        await update.message.reply_text(crypto, parse_mode='Markdown')
    
    else:
        # Default response for unrecognized messages
        if bot_settings.get("auto_reply", True):
            responses = [
                "I'm here to help! Use the menu for quick access to tools.",
                "Need assistance? Try the Quick Tools or Entertainment menus!",
                "I can help with weather, crypto, news, jokes and more!",
                "Check out the main menu for all available features! 🚀"
            ]
            await update.message.reply_text(random.choice(responses))
    
    DataManager.save_data(USER_FILE, user_data)

# --- Group Handlers ---
async def group_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not bot_settings.get("welcome_message", True):
        return
    
    new_members = update.message.new_chat_members
    for member in new_members:
        if member.id == context.bot.id:
            # Bot added to group
            group_id = str(update.effective_chat.id)
            group_data[group_id] = {
                "title": update.effective_chat.title,
                "added_date": datetime.now().isoformat(),
                "member_count": update.effective_chat.get_member_count()
            }
            DataManager.save_data(GROUP_FILE, group_data)
            
            await update.message.reply_text(
                "🤖 Thanks for adding me! I provide:\n"
                "• Live weather & crypto updates 🌤️💰\n"
                "• Entertainment & jokes 🎮😂\n"
                "• News & facts 📰📚\n"
                "• Group management tools ⚙️\n\n"
                "Use /help to see all features!"
            )
        else:
            # New user joined
            welcome_messages = [
                f"👋 Welcome {member.first_name}! Feel free to explore my features!",
                f"🎉 Hello {member.first_name}! I'm here to help with updates and entertainment!",
                f"🤖 Welcome aboard {member.first_name}! Use /help to see what I can do!"
            ]
            await update.message.reply_text(random.choice(welcome_messages))

# --- Admin Command ---
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Admin access required!")
        return
    
    user_count = len(user_data)
    group_count = len(group_data)
    active_users = len([u for u in user_data.values() if datetime.fromisoformat(u.get('last_seen', datetime.now().isoformat())) > datetime.now() - timedelta(days=1)])
    
    admin_text = f"""
👨‍💻 *Admin Panel*

📊 *Statistics:*
• Total Users: {user_count}
• Active Users (24h): {active_users}
• Groups: {group_count}

🔧 *Available Tools:*
• Broadcast messages
• User management
• System settings
• Bot maintenance
"""
    await update.message.reply_text(
        admin_text,
        reply_markup=Keyboards.admin_panel(),
        parse_mode='Markdown'
    )

# --- Graceful Shutdown ---
def signal_handler(signum, frame):
    logger.info("Received shutdown signal. Saving data...")
    DataManager.save_data(USER_FILE, user_data)
    DataManager.save_data(GROUP_FILE, group_data)
    DataManager.save_data(SETTINGS_FILE, bot_settings)
    logger.info("Data saved. Shutting down...")
    sys.exit(0)

# --- Main Application with Conflict Resolution ---
def main():
    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Create application with conflict prevention
    application = Application.builder().token(TOKEN).build()
    
    # Add error handler for conflicts
    async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        logger.error(f"Exception while handling an update: {context.error}")
        
        if "Conflict" in str(context.error):
            logger.warning("Conflict detected - possibly multiple instances running")
            # Don't crash on conflict, just log it
    
    application.add_error_handler(error_handler)
    
    # Command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("admin", admin_command))
    application.add_handler(CommandHandler("main", start_command))  # Alias for start
    
    # Button handlers
    application.add_handler(CallbackQueryHandler(button_handler))
    
    # Message handlers
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_main_menu))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Group handlers
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, group_welcome))
    
    # Set bot commands
    async def post_init(application: Application):
        await application.bot.set_my_commands([
            BotCommand("start", "Start the bot"),
            BotCommand("help", "Show help guide"),
            BotCommand("status", "Check bot status"),
            BotCommand("admin", "Admin panel")
        ])
        logger.info("Bot commands set successfully")
    
    application.post_init = post_init
    
    # Startup message
    logger.info("🤖 Starting Advanced Assistant Bot...")
    logger.info(f"👤 Admin ID: {ADMIN_ID}")
    logger.info(f"📊 Loaded users: {len(user_data)}")
    logger.info(f"💬 Loaded groups: {len(group_data)}")
    
    try:
        # Start with conflict resolution
        application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True,  # Important: Avoid processing old updates
            close_loop=False
        )
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        # Save data before exiting
        DataManager.save_data(USER_FILE, user_data)
        DataManager.save_data(GROUP_FILE, group_data)
        DataManager.save_data(SETTINGS_FILE, bot_settings)
        sys.exit(1)

if __name__ == "__main__":
    main()
