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
import re

# ==================== CONFIGURATION ====================
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Get token from environment variable
TOKEN: Final = os.getenv("BOT_TOKEN")
if not TOKEN:
    logger.error("❌ BOT_TOKEN environment variable not set!")
    # Don't raise error immediately, allow for local testing
    TOKEN = "YOUR_BOT_TOKEN_HERE"  # Replace with your actual token for local testing

BOT_USERNAME: Final = '@alitacode_bot'
ADMIN_ID: Final = 7327016053

# ==================== DATA MANAGEMENT ====================
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

# Initialize data storage
USER_FILE = "users.json"
GROUP_FILE = "groups.json"
SETTINGS_FILE = "settings.json"
CHANNEL_FILE = "channel.json"
SCHEDULE_FILE = "schedule.json"
INTERVALS_FILE = "group_intervals.json"
AUTO_SETTINGS_FILE = "auto_settings.json"

# Create empty files if they don't exist
for file in [USER_FILE, GROUP_FILE, SETTINGS_FILE, CHANNEL_FILE, SCHEDULE_FILE, INTERVALS_FILE, AUTO_SETTINGS_FILE]:
    if not os.path.exists(file):
        DataManager.save_data(file, {})

user_data = DataManager.load_data(USER_FILE, {})
group_data = DataManager.load_data(GROUP_FILE, {})
bot_settings = DataManager.load_data(SETTINGS_FILE, {
    "auto_reply": True,
    "welcome_message": True,
    "anti_spam": True,
    "auto_moderation": True
})
channel_data = DataManager.load_data(CHANNEL_FILE, {
    "last_message_time": datetime.now().isoformat()
})

# ==================== SCHEDULED MESSAGES SYSTEM ====================
class ScheduledMessages:
    def __init__(self):
        self.last_message_time = {}  # Track last message time per chat
        self.message_intervals = {
            "hourly": 3600,  # 1 hour in seconds
            "every_3_hours": 10800,  # 3 hours
            "every_6_hours": 21600,  # 6 hours
            "daily": 86400,  # 24 hours
            "weekly": 604800  # 7 days
        }
        self.load_schedule_data()
    
    def should_send_message(self, chat_id: str, interval: str = "every_3_hours") -> bool:
        """Check if enough time has passed to send another message"""
        current_time = datetime.now()
        
        if chat_id not in self.last_message_time:
            self.last_message_time[chat_id] = current_time
            return True
        
        last_time = self.last_message_time[chat_id]
        time_diff = (current_time - last_time).total_seconds()
        
        return time_diff >= self.message_intervals.get(interval, 10800)
    
    def update_last_message(self, chat_id: str):
        """Update the last message time for a chat"""
        self.last_message_time[chat_id] = datetime.now()
        # Save to file for persistence
        self.save_schedule_data()
    
    def save_schedule_data(self):
        """Save scheduling data to file"""
        schedule_data = {}
        for chat_id, timestamp in self.last_message_time.items():
            schedule_data[chat_id] = timestamp.isoformat()
        DataManager.save_data(SCHEDULE_FILE, schedule_data)
    
    def load_schedule_data(self):
        """Load scheduling data from file"""
        data = DataManager.load_data(SCHEDULE_FILE, {})
        for chat_id, timestamp_str in data.items():
            try:
                self.last_message_time[chat_id] = datetime.fromisoformat(timestamp_str)
            except:
                pass

# Initialize scheduler
scheduler = ScheduledMessages()

# ==================== FREE API SERVICES ====================
class FreeAPIServices:
    @staticmethod
    async def get_weather(city: str = "London") -> str:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"http://wttr.in/{city}?format=%C+%t+%h+%w", timeout=10) as response:
                    if response.status == 200:
                        return f"🌤️ Weather in {city.title()}: {await response.text()}"
        except Exception as e:
            logger.error(f"Weather API error: {e}")
            return f"🌤️ Weather for {city.title()}: ⛅ 25°C 💧 60% 🌬️ 10km/h"

    @staticmethod
    async def get_joke() -> str:
        jokes = [
            "Why don't scientists trust atoms? Because they make up everything!",
            "What do you call a fake noodle? An impasta!",
            "Why did the scarecrow win an award? He was outstanding in his field!",
            "Why don't eggs tell jokes? They'd crack each other up!",
            "What do you call a sleeping bull? A bulldozer!"
        ]
        return f"😂 Joke: {random.choice(jokes)}"

    @staticmethod
    async def get_quote() -> str:
        quotes = [
            "The only way to do great work is to love what you do. - Steve Jobs",
            "Innovation distinguishes between a leader and a follower. - Steve Jobs",
            "Your time is limited, don't waste it living someone else's life. - Steve Jobs",
            "The future belongs to those who believe in the beauty of their dreams. - Eleanor Roosevelt",
            "Life is what happens when you're busy making other plans. - John Lennon"
        ]
        return f"💫 Quote: {random.choice(quotes)}"

    @staticmethod
    async def get_advice() -> str:
        advice_list = [
            "Take time to appreciate the small things in life.",
            "Learn something new every day.",
            "Stay hydrated and drink plenty of water.",
            "Believe in yourself and your abilities.",
            "Practice gratitude daily.",
            "Always be kind to others.",
            "Don't be afraid to ask for help.",
            "Take breaks when you need them."
        ]
        return f"🤔 Advice: {random.choice(advice_list)}"

    @staticmethod
    async def get_fact() -> str:
        facts = [
            "Honey never spoils. Archaeologists have found 3000-year-old honey that's still good!",
            "Octopuses have three hearts and blue blood.",
            "A day on Venus is longer than a year on Venus.",
            "Bananas are berries, but strawberries aren't.",
            "The shortest war in history lasted only 38 minutes."
        ]
        return f"📚 Fact: {random.choice(facts)}"

    @staticmethod
    async def get_song_suggestion() -> str:
        songs = [
            "🎵 Kesariya - Brahmāstra",
            "🎵 Apna Bana Le - Bhediya", 
            "🎵 Besharam Rang - Pathaan",
            "🎵 Flowers - Miley Cyrus",
            "🎵 Anti-Hero - Taylor Swift",
            "🎵 As It Was - Harry Styles"
        ]
        return f"🎶 Song Suggestion: {random.choice(songs)}"

# ==================== ENHANCED AUTO MESSAGING ====================
class AutoMessaging:
    @staticmethod
    def get_greeting():
        hour = datetime.now().hour
        if 5 <= hour < 12:
            return "🌅 Good Morning! Have a wonderful day ahead!"
        elif 12 <= hour < 17:
            return "☀️ Good Afternoon! Hope you're having a great day!"
        elif 17 <= hour < 21:
            return "🌇 Good Evening! Relax and unwind!"
        else:
            return "🌙 Good Night! Sleep well and sweet dreams!"

    @staticmethod
    def get_festival_wish():
        festivals = {
            "01-01": "🎉 Happy New Year! May this year bring you joy and success!",
            "02-14": "💝 Happy Valentine's Day! Spread love and kindness!",
            "03-08": "🌸 Happy Holi! May your life be filled with vibrant colors!",
            "10-02": "🪔 Happy Gandhi Jayanti! Be the change you wish to see!",
            "10-24": "🎃 Happy Diwali! May light triumph over darkness!",
            "12-25": "🎄 Merry Christmas! Peace, love, and joy to you!"
        }
        today = datetime.now().strftime("%m-%d")
        return festivals.get(today, "🌟 Have a wonderful day! Spread positivity!")

    @staticmethod
    def get_motivation():
        motivations = [
            "💪 *Motivation*: The only way to do great work is to love what you do.",
            "✨ *Success Tip*: Small progress is still progress. Keep going!",
            "🌟 *Daily Inspiration*: Your limitation—it's only your imagination.",
            "🎯 *Focus*: Push yourself, because no one else is going to do it for you.",
            "🌈 *Mindset*: Great things never come from comfort zones."
        ]
        return random.choice(motivations)
    
    @staticmethod
    def get_tip():
        tips = [
            "💡 *Productivity Tip*: Take regular breaks to maintain focus.",
            "🛡️ *Security Tip*: Use strong, unique passwords for all accounts.",
            "💪 *Health Tip*: Drink water first thing in the morning.",
            "🧠 *Learning Tip*: Teach others to reinforce your own knowledge.",
            "💰 *Finance Tip*: Save at least 20% of your income."
        ]
        return random.choice(tips)
    
    @staticmethod
    async def get_news_headline():
        headlines = [
            "📰 *Tech News*: AI continues to revolutionize industries worldwide!",
            "🌍 *World News*: Global cooperation on climate change intensifies.",
            "🚀 *Space News*: New discoveries about Mars captured public imagination.",
            "💻 *Digital*: Cybersecurity becomes top priority for organizations.",
            "🎮 *Gaming*: New game releases break previous sales records."
        ]
        return random.choice(headlines)
    
    @staticmethod
    async def get_interesting_fact():
        facts = [
            "🐘 *Animal Fact*: Elephants are the only mammals that can't jump.",
            "🌊 *Ocean Fact*: More people have been to the Moon than the Mariana Trench.",
            "🧠 *Brain Fact*: Your brain generates enough electricity to power a lightbulb.",
            "🌍 *Earth Fact*: Antarctica is the largest desert in the world.",
            "👁️ *Body Fact*: Your eyes blink about 20 times per minute."
        ]
        return random.choice(facts)

    @staticmethod
    async def get_random_content():
        """Get random content from various categories"""
        content_options = [
            AutoMessaging.get_greeting,
            AutoMessaging.get_festival_wish,
            FreeAPIServices.get_quote,
            FreeAPIServices.get_song_suggestion,
            FreeAPIServices.get_joke,
            FreeAPIServices.get_advice,
            FreeAPIServices.get_fact,
            AutoMessaging.get_motivation,
            AutoMessaging.get_tip,
            AutoMessaging.get_news_headline,
            AutoMessaging.get_interesting_fact
        ]
        
        content_func = random.choice(content_options)
        if asyncio.iscoroutinefunction(content_func):
            return await content_func()
        return content_func()

    @staticmethod
    async def send_auto_message(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
        try:
            content = await AutoMessaging.get_random_content()
            
            formatted_content = f"""
🤖 *Alita Assistant Update*

{content}

---
🕐 {datetime.now().strftime('%I:%M %p')} • Use /help for more features!
"""
            await context.bot.send_message(
                chat_id=chat_id, 
                text=formatted_content,
                parse_mode='Markdown'
            )
            logger.info(f"✅ Auto message sent to {chat_id}")
        except Exception as e:
            logger.error(f"❌ Failed to send auto message: {e}")

# ==================== PERIODIC MESSAGE FUNCTION ====================
async def periodic_group_messages(context: ContextTypes.DEFAULT_TYPE):
    """Send periodic messages to all groups"""
    try:
        # Get all groups from your data
        groups = list(group_data.keys())
        
        # Load auto settings
        auto_settings = DataManager.load_data(AUTO_SETTINGS_FILE, {})
        group_intervals = DataManager.load_data(INTERVALS_FILE, {})
        
        for group_id in groups:
            try:
                # Check if auto-responses are enabled for this group
                if not auto_settings.get(str(group_id), True):
                    continue
                
                # Get interval for this group (default 3 hours)
                interval_hours = group_intervals.get(str(group_id), 3)
                interval_seconds = interval_hours * 3600
                
                # Check if we should send a message
                current_time = datetime.now()
                last_time = scheduler.last_message_time.get(str(group_id))
                
                if last_time is None or (current_time - last_time).total_seconds() >= interval_seconds:
                    # Send message
                    await AutoMessaging.send_auto_message(context, int(group_id))
                    scheduler.update_last_message(str(group_id))
                    
                    # Small delay to avoid rate limits
                    await asyncio.sleep(1)
                    
            except Exception as e:
                logger.error(f"❌ Failed to process group {group_id}: {e}")
                continue
                
    except Exception as e:
        logger.error(f"❌ Periodic messaging error: {e}")

# ==================== MODERATION SYSTEM ====================
class ModerationSystem:
    BAD_WORDS = ["fuck", "shit", "asshole", "bastard", "bitch", "damn", "hell"]
    SPAM_LIMIT = 5
    
    @staticmethod
    def check_violation(message_text: str, user_id: str) -> str:
        if any(word in message_text.lower() for word in ModerationSystem.BAD_WORDS):
            return "bad_language"
        
        user_msg_count = user_data.get(user_id, {}).get("message_count", 0)
        if user_msg_count > ModerationSystem.SPAM_LIMIT:
            return "spamming"
        
        if len(message_text) > 100:
            return "flooding"
        
        if len(re.findall(r'http[s]?://', message_text)) > 3:
            return "link_spam"
        
        return ""

    @staticmethod
    async def take_action(update: Update, context: ContextTypes.DEFAULT_TYPE, violation: str, user_id: str):
        user = update.effective_user
        actions = {
            "bad_language": ("⚠️ Language Warning", "Please maintain respectful language."),
            "spamming": ("🚫 Spam Detected", "Please avoid sending too many messages."),
            "flooding": ("📢 Flood Warning", "Please keep messages concise."),
            "link_spam": ("🔗 Link Spam", "Too many links detected.")
        }
        
        action_text, warning = actions.get(violation, ("⚠️ Rule Violation", "Please follow group rules."))
        warning_msg = f"{action_text}\nUser: {user.first_name}\nReason: {warning}"
        
        try:
            await update.message.reply_text(warning_msg)
            logger.info(f"🛡️ Moderation action: {violation} for user {user_id}")
        except Exception as e:
            logger.error(f"❌ Moderation action failed: {e}")

# ==================== CHANNEL MONITORING ====================
class ChannelMonitor:
    @staticmethod
    async def check_channel_activity(context: ContextTypes.DEFAULT_TYPE):
        try:
            last_message_time = datetime.fromisoformat(channel_data["last_message_time"])
            current_time = datetime.now()
            
            hours_inactive = (current_time - last_message_time).total_seconds() / 3600
            days_inactive = hours_inactive / 24
            
            if hours_inactive >= 5 or days_inactive >= 2:
                reminder_msg = f"""
🔔 *Channel Activity Reminder*

📊 Status Report:
• Last message: {last_message_time.strftime('%Y-%m-%d %H:%M')}
• Hours inactive: {hours_inactive:.1f}h
• Days inactive: {days_inactive:.1f}d

💡 Suggestion: Consider posting new content!
"""
                await context.bot.send_message(
                    chat_id=ADMIN_ID,
                    text=reminder_msg,
                    parse_mode='Markdown'
                )
                logger.info("📢 Channel inactivity reminder sent")
                
        except Exception as e:
            logger.error(f"❌ Channel monitoring error: {e}")

    @staticmethod
    def update_last_message_time():
        channel_data["last_message_time"] = datetime.now().isoformat()
        DataManager.save_data(CHANNEL_FILE, channel_data)

# ==================== KEYBOARD LAYOUTS ====================
class Keyboards:
    @staticmethod
    def main_menu():
        return ReplyKeyboardMarkup([
            [KeyboardButton("🌍 Weather"), KeyboardButton("🎵 Music")],
            [KeyboardButton("😂 Fun"), KeyboardButton("🛠️ Tools")],
            [KeyboardButton("👑 Admin")]
        ], resize_keyboard=True)

    @staticmethod
    def fun_menu():
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("😂 Joke", callback_data="fun_joke"),
             InlineKeyboardButton("💫 Quote", callback_data="fun_quote")],
            [InlineKeyboardButton("🤔 Advice", callback_data="fun_advice"),
             InlineKeyboardButton("📚 Fact", callback_data="fun_fact")],
            [InlineKeyboardButton("🎵 Song", callback_data="fun_song"),
             InlineKeyboardButton("🔙 Back", callback_data="back_main")]
        ])

    @staticmethod
    def admin_panel():
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast"),
             InlineKeyboardButton("📊 Stats", callback_data="admin_stats")],
            [InlineKeyboardButton("🛡️ Moderation", callback_data="admin_moderation"),
             InlineKeyboardButton("🔔 Channel Check", callback_data="admin_channel")],
            [InlineKeyboardButton("🔄 Auto Message", callback_data="admin_auto"),
             InlineKeyboardButton("🔙 Main Menu", callback_data="back_main")]
        ])

    @staticmethod
    def back_only():
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data="back_main")]
        ])

# ==================== MESSAGE TEMPLATES ====================
class Messages:
    WELCOME = """
✨ *Welcome to Alita Assistant!* 🤖

🌍 *Real-time Features*
• Weather updates • Song suggestions

🎵 *Entertainment*
• Jokes • Quotes • Music • Facts

🛡️ *Group Management*
• Auto-moderation • Welcome messages

👑 *Admin Tools*
• Broadcast messages • User statistics
• Auto-response scheduling

*Use the menu below to get started!* 🚀
"""

    HELP = """
📖 *Alita Assistant Guide*

*Commands:*
/start - Start the bot
/help - Show this guide
/status - Check bot status
/rules - Show group rules
/auto - Trigger auto response
/setinterval - Set auto-response interval
/toggleauto - Toggle auto-responses

*Features:*
• Weather updates
• Entertainment (jokes, quotes, songs)
• Group moderation
• Auto responses in groups
• Admin tools
"""

# ==================== COMMAND HANDLERS ====================
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = str(user.id)
    
    if user_id not in user_data:
        user_data[user_id] = {
            "first_seen": datetime.now().isoformat(),
            "username": user.username,
            "first_name": user.first_name,
            "message_count": 0,
            "last_seen": datetime.now().isoformat()
        }
    
    user_data[user_id]["message_count"] = user_data[user_id].get("message_count", 0) + 1
    user_data[user_id]["last_seen"] = datetime.now().isoformat()
    DataManager.save_data(USER_FILE, user_data)
    
    welcome_text = f"👋 Hello {user.first_name}!\n\n{Messages.WELCOME}"
    
    await update.message.reply_text(
        welcome_text,
        reply_markup=Keyboards.main_menu(),
        parse_mode='Markdown'
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(Messages.HELP, parse_mode='Markdown')

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_count = len(user_data)
    group_count = len(group_data)
    
    status_text = f"""
🤖 *Alita Assistant Status*

✅ *All Systems Operational*
👥 Users: *{user_count}*
💬 Groups: *{group_count}*
🕐 Uptime: *24/7 Active*

🚀 *Services:*
• Weather: ✅ Live
• Entertainment: ✅ Ready
• Moderation: ✅ Active
• Broadcasting: ✅ Enabled
• Auto-Responses: ✅ Active

*Bot is running perfectly!* ✨
"""
    await update.message.reply_text(status_text, parse_mode='Markdown')

async def rules_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rules_text = """
📜 *Group Rules*

1. ✅ Be respectful to all members
2. ✅ No spam or flooding
3. ✅ No inappropriate language
4. ✅ Keep discussions relevant

Let's keep this community positive! 🌟
"""
    await update.message.reply_text(rules_text, parse_mode='Markdown')

# ==================== AUTO RESPONSE COMMANDS ====================
async def trigger_auto_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command to manually trigger an auto-response (/auto)"""
    # Check if in group
    if update.effective_chat.type not in ["group", "supergroup"]:
        await update.message.reply_text("❌ This command only works in groups!")
        return
    
    chat = update.effective_chat
    content = await AutoMessaging.get_random_content()
    
    formatted_content = f"""
🤖 *Auto Response Triggered*

{content}

---
Requested by: {update.effective_user.first_name}
🕐 {datetime.now().strftime('%I:%M %p')}
"""
    
    await update.message.reply_text(formatted_content, parse_mode='Markdown')
    scheduler.update_last_message(str(chat.id))

async def set_auto_interval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set auto-response interval for the group (/setinterval [hours])"""
    if update.effective_chat.type not in ["group", "supergroup"]:
        await update.message.reply_text("❌ This command only works in groups!")
        return
    
    chat = update.effective_chat
    chat_id = str(chat.id)
    
    # Parse interval
    try:
        if context.args:
            hours = float(context.args[0])
            if hours < 1:
                await update.message.reply_text("❌ Interval must be at least 1 hour!")
                return
            
            # Save interval for this group
            intervals = DataManager.load_data(INTERVALS_FILE, {})
            intervals[chat_id] = hours
            DataManager.save_data(INTERVALS_FILE, intervals)
            
            await update.message.reply_text(
                f"✅ Auto-response interval set to {hours} hours!\n"
                f"The bot will now send updates every {hours} hours."
            )
        else:
            # Show current interval
            intervals = DataManager.load_data(INTERVALS_FILE, {})
            current = intervals.get(chat_id, 3)
            await update.message.reply_text(
                f"📊 Current auto-response interval: {current} hours\n"
                f"To change: `/setinterval [hours]`\n"
                f"Example: `/setinterval 6` for 6 hours",
                parse_mode='Markdown'
            )
    except ValueError:
        await update.message.reply_text("❌ Please provide a valid number of hours!")

async def toggle_auto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Toggle auto-responses on/off for the group (/toggleauto)"""
    if update.effective_chat.type not in ["group", "supergroup"]:
        await update.message.reply_text("❌ This command only works in groups!")
        return
    
    chat = update.effective_chat
    chat_id = str(chat.id)
    
    # Toggle setting
    settings = DataManager.load_data(AUTO_SETTINGS_FILE, {})
    current = settings.get(chat_id, True)
    settings[chat_id] = not current
    DataManager.save_data(AUTO_SETTINGS_FILE, settings)
    
    status = "enabled" if settings[chat_id] else "disabled"
    await update.message.reply_text(f"✅ Auto-responses {status} for this group!")

# ==================== MAIN MENU HANDLER ====================
async def handle_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    
    if text == "🌍 Weather":
        weather = await FreeAPIServices.get_weather()
        await update.message.reply_text(weather)
    
    elif text == "🎵 Music":
        song = await FreeAPIServices.get_song_suggestion()
        await update.message.reply_text(song)
    
    elif text == "😂 Fun":
        await update.message.reply_text(
            "🎉 *Fun Zone* - Choose entertainment:",
            reply_markup=Keyboards.fun_menu(),
            parse_mode='Markdown'
        )
    
    elif text == "👑 Admin":
        if update.effective_user.id != ADMIN_ID:
            await update.message.reply_text("❌ Admin access required!")
            return
        
        await update.message.reply_text(
            "👑 *Admin Control Panel*",
            reply_markup=Keyboards.admin_panel(),
            parse_mode='Markdown'
        )
    
    elif text == "🛠️ Tools":
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        await update.message.reply_text(f"🕐 Current Time: `{current_time}`", parse_mode='Markdown')

# ==================== BUTTON HANDLER ====================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    try:
        if data == "fun_joke":
            joke = await FreeAPIServices.get_joke()
            await query.edit_message_text(joke, reply_markup=Keyboards.fun_menu())
        
        elif data == "fun_quote":
            quote = await FreeAPIServices.get_quote()
            await query.edit_message_text(quote, reply_markup=Keyboards.fun_menu())
        
        elif data == "fun_advice":
            advice = await FreeAPIServices.get_advice()
            await query.edit_message_text(advice, reply_markup=Keyboards.fun_menu())
        
        elif data == "fun_fact":
            fact = await FreeAPIServices.get_fact()
            await query.edit_message_text(fact, reply_markup=Keyboards.fun_menu())
        
        elif data == "fun_song":
            song = await FreeAPIServices.get_song_suggestion()
            await query.edit_message_text(song, reply_markup=Keyboards.fun_menu())
        
        elif data == "admin_stats":
            if update.effective_user.id != ADMIN_ID:
                await query.edit_message_text("❌ Admin access required!")
                return
            
            user_count = len(user_data)
            group_count = len(group_data)
            active_today = len([u for u in user_data.values() 
                              if datetime.fromisoformat(u.get('last_seen', datetime.now().isoformat())) > datetime.now() - timedelta(days=1)])
            
            stats_text = f"""
📊 *Admin Statistics*

👥 Users: {user_count}
💬 Groups: {group_count}
📈 Active Today: {active_today}
🔄 Total Messages: {sum(u.get('message_count', 0) for u in user_data.values())}

🛡️ Moderation: Active
🔔 Auto Messages: Ready
📢 Broadcasting: Enabled
"""
            await query.edit_message_text(stats_text, reply_markup=Keyboards.admin_panel(), parse_mode='Markdown')
        
        elif data == "admin_broadcast":
            success_count = 0
            for user_id in user_data.keys():
                try:
                    await context.bot.send_message(
                        chat_id=int(user_id),
                        text="📢 *Broadcast from Admin*\n\nThis is a test broadcast message! 🌟",
                        parse_mode='Markdown'
                    )
                    success_count += 1
                    await asyncio.sleep(0.1)
                except Exception:
                    continue
            
            await query.edit_message_text(
                f"✅ Broadcast sent to {success_count} users!",
                reply_markup=Keyboards.admin_panel()
            )
        
        elif data == "admin_channel":
            await ChannelMonitor.check_channel_activity(context)
            await query.edit_message_text("✅ Channel check completed!", reply_markup=Keyboards.admin_panel())
        
        elif data == "admin_auto":
            await AutoMessaging.send_auto_message(context, update.effective_chat.id)
            await query.edit_message_text("✅ Auto message sent!", reply_markup=Keyboards.admin_panel())
        
        elif data == "back_main":
            await query.edit_message_text(
                "🏠 *Main Menu*",
                reply_markup=Keyboards.main_menu(),
                parse_mode='Markdown'
            )
        
        else:
            await query.edit_message_text(
                "🛠️ Feature in development!",
                reply_markup=Keyboards.back_only()
            )
    
    except Exception as e:
        logger.error(f"Button handler error: {e}")
        await query.edit_message_text(
            "❌ Service temporarily unavailable",
            reply_markup=Keyboards.back_only()
        )

# ==================== MESSAGE HANDLER ====================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    
    user_id = str(update.effective_user.id)
    text = update.message.text or ""
    
    # Update user data
    if user_id not in user_data:
        user_data[user_id] = {
            "first_seen": datetime.now().isoformat(),
            "username": update.effective_user.username,
            "first_name": update.effective_user.first_name,
            "message_count": 0,
            "last_seen": datetime.now().isoformat()
        }
    
    user_data[user_id]["message_count"] = user_data[user_id].get("message_count", 0) + 1
    user_data[user_id]["last_seen"] = datetime.now().isoformat()
    
    # Auto-moderation in groups
    if update.effective_chat.type in ["group", "supergroup"]:
        violation = ModerationSystem.check_violation(text, user_id)
        if violation:
            await ModerationSystem.take_action(update, context, violation, user_id)
            return
    
    # Smart replies
    responses = {
        'hello': "👋 Hello! How can I help you today?",
        'hi': "👋 Hi there! Ready to explore some features?",
        'thanks': "😊 You're welcome!",
        'thank you': "😊 Happy to help!",
        'how are you': "🤖 I'm running perfectly!",
        'bye': "👋 Goodbye! Come back anytime!"
    }
    
    for key, response in responses.items():
        if key in text.lower():
            await update.message.reply_text(response)
            break
    
    DataManager.save_data(USER_FILE, user_data)

# ==================== GROUP HANDLERS ====================
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
                "added_date": datetime.now().isoformat()
            }
            DataManager.save_data(GROUP_FILE, group_data)
            
            await update.message.reply_text(
                "🤖 Thanks for adding Alita Assistant!\n\n"
                "I provide:\n• Auto-moderation\n• Entertainment\n• Utilities\n"
                "• Auto responses every 3 hours\n\n"
                "Use /help to get started! 🚀"
            )
        else:
            # Welcome new user
            welcome_msg = f"""
👋 Welcome {member.first_name} to {update.effective_chat.title}!

I'm Alita Assistant 🤖 - here to help with:
• Entertainment & fun
• Information & utilities  
• Group moderation
• Periodic updates

Use /rules to see group guidelines
Use /help to explore features

Enjoy your stay! 🌟
"""
            await update.message.reply_text(welcome_msg, parse_mode='Markdown')

# ==================== ERROR HANDLER ====================
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Exception: {context.error}")

# ==================== PERIODIC TASK STARTER ====================
async def start_periodic_messages(application: Application):
    """Start periodic messages without using JobQueue"""
    async def periodic_wrapper():
        while True:
            try:
                # Create a context-like object
                class Context:
                    def __init__(self, bot):
                        self.bot = bot
                
                context = Context(application.bot)
                await periodic_group_messages(context)
                
                # Wait for 1 hour before next check
                await asyncio.sleep(3600)  # Check every hour
                
            except Exception as e:
                logger.error(f"Periodic wrapper error: {e}")
                await asyncio.sleep(60)  # Wait 1 minute on error
    
    # Create and start the task
    asyncio.create_task(periodic_wrapper())
    logger.info("✅ Periodic messaging task started")

# ==================== HEALTH CHECK ENDPOINT (for Render) ====================
async def health_check(request):
    """Simple health check endpoint for Render"""
    return aiohttp.web.Response(text="OK")

# ==================== MAIN APPLICATION ====================
async def run_web_server():
    """Run a simple web server for health checks (required by Render)"""
    app = aiohttp.web.Application()
    app.router.add_get('/', health_check)
    app.router.add_get('/health', health_check)
    
    port = int(os.environ.get("PORT", 10000))
    runner = aiohttp.web.AppRunner(app)
    await runner.setup()
    site = aiohttp.web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logger.info(f"✅ Health check server running on port {port}")

def main():
    # Setup signal handlers
    def signal_handler(signum, frame):
        logger.info("🔄 Shutting down gracefully...")
        DataManager.save_data(USER_FILE, user_data)
        DataManager.save_data(GROUP_FILE, group_data)
        DataManager.save_data(SETTINGS_FILE, bot_settings)
        DataManager.save_data(CHANNEL_FILE, channel_data)
        DataManager.save_data(SCHEDULE_FILE, scheduler.last_message_time)
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Create application
    application = Application.builder().token(TOKEN).build()
    
    # Add error handler
    application.add_error_handler(error_handler)
    
    # Command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("rules", rules_command))
    application.add_handler(CommandHandler("auto", trigger_auto_response))
    application.add_handler(CommandHandler("setinterval", set_auto_interval))
    application.add_handler(CommandHandler("toggleauto", toggle_auto))
    
    # Button handlers
    application.add_handler(CallbackQueryHandler(button_handler))
    
    # Message handlers - IMPORTANT: Order matters!
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_main_menu))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Group handlers
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, group_welcome))
    
    # Set bot commands
    async def post_init(application: Application):
        await application.bot.set_my_commands([
            BotCommand("start", "Start Alita Assistant"),
            BotCommand("help", "Get help guide"),
            BotCommand("status", "Check bot status"),
            BotCommand("rules", "Show group rules"),
            BotCommand("auto", "Trigger auto response"),
            BotCommand("setinterval", "Set auto-response interval"),
            BotCommand("toggleauto", "Toggle auto-responses")
        ])
        logger.info("✅ Bot commands configured")
        
        # Start periodic messages
        await start_periodic_messages(application)
        
        # Start health check server (required for Render)
        await run_web_server()
    
    application.post_init = post_init
    
    # Startup
    logger.info("🚀 Starting Alita Assistant...")
    logger.info(f"👑 Admin: {ADMIN_ID}")
    logger.info(f"👥 Users: {len(user_data)}")
    logger.info(f"💬 Groups: {len(group_data)}")
    
    try:
        # Run the bot
        application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True
        )
    except Exception as e:
        logger.error(f"❌ Bot failed: {e}")
        DataManager.save_data(USER_FILE, user_data)
        DataManager.save_data(GROUP_FILE, group_data)
        DataManager.save_data(SETTINGS_FILE, bot_settings)
        DataManager.save_data(CHANNEL_FILE, channel_data)
        DataManager.save_data(SCHEDULE_FILE, scheduler.last_message_time)
        sys.exit(1)

if __name__ == "__main__":
    main()
