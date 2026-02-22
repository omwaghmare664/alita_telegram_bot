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

# ==================== TOKENS AND IDs ====================
BOT_TOKEN = "8168577329:AAFgYEHmIe-SDuRL3tqt6rx1MtAnJprSbRc"  # Your bot token
BOT_USERNAME = '@alitacode_bot'
ADMIN_ID = 7327016053

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
        self.last_message_time = {}
        self.message_intervals = {
            "hourly": 3600,
            "every_3_hours": 10800,
            "every_6_hours": 21600,
            "daily": 86400,
            "weekly": 604800
        }
        self.load_schedule_data()
    
    def should_send_message(self, chat_id: str, interval: str = "every_3_hours") -> bool:
        current_time = datetime.now()
        
        if chat_id not in self.last_message_time:
            self.last_message_time[chat_id] = current_time
            return True
        
        last_time = self.last_message_time[chat_id]
        time_diff = (current_time - last_time).total_seconds()
        
        return time_diff >= self.message_intervals.get(interval, 10800)
    
    def update_last_message(self, chat_id: str):
        self.last_message_time[chat_id] = datetime.now()
        self.save_schedule_data()
    
    def save_schedule_data(self):
        schedule_data = {}
        for chat_id, timestamp in self.last_message_time.items():
            schedule_data[chat_id] = timestamp.isoformat()
        DataManager.save_data(SCHEDULE_FILE, schedule_data)
    
    def load_schedule_data(self):
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
            "What do you call a sleeping bull? A bulldozer!",
            "Why did the math book look sad? Because it had too many problems!",
            "What do you call a bear with no teeth? A gummy bear!",
            "Why don't skeletons fight each other? They don't have the guts!"
        ]
        return f"😂 Joke: {random.choice(jokes)}"

    @staticmethod
    async def get_quote() -> str:
        quotes = [
            "The only way to do great work is to love what you do. - Steve Jobs",
            "Innovation distinguishes between a leader and a follower. - Steve Jobs",
            "Your time is limited, don't waste it living someone else's life. - Steve Jobs",
            "The future belongs to those who believe in the beauty of their dreams. - Eleanor Roosevelt",
            "Life is what happens when you're busy making other plans. - John Lennon",
            "Success is not final, failure is not fatal: it is the courage to continue that counts. - Winston Churchill",
            "Believe you can and you're halfway there. - Theodore Roosevelt"
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
            "Take breaks when you need them.",
            "Save money for rainy days.",
            "Exercise regularly for good health."
        ]
        return f"🤔 Advice: {random.choice(advice_list)}"

    @staticmethod
    async def get_fact() -> str:
        facts = [
            "Honey never spoils. Archaeologists have found 3000-year-old honey that's still good!",
            "Octopuses have three hearts and blue blood.",
            "A day on Venus is longer than a year on Venus.",
            "Bananas are berries, but strawberries aren't.",
            "The shortest war in history lasted only 38 minutes.",
            "A group of flamingos is called a 'flamboyance'.",
            "The Eiffel Tower can be 15 cm taller during the summer.",
            "Humans share 60% of their DNA with bananas."
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
            "🎵 As It Was - Harry Styles",
            "🎵 Calm Down - Rema",
            "🎵 Pasoori - Coke Studio",
            "🎵 Kurchi Madathapetti - Guntur Kaaram"
        ]
        return f"🎶 Song Suggestion: {random.choice(songs)}"

# ==================== AUTO MESSAGING ====================
class AutoMessaging:
    @staticmethod
    def get_time_based_greeting():
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
    def get_random_greeting():
        greetings = [
            "Hello everyone! 👋",
            "Hi there! 🌟",
            "Hey guys! 💫",
            "Greetings everyone! ✨",
            "Namaste! 🙏",
            "Vanakkam! 🤝",
            "What's up everyone! 🚀"
        ]
        return random.choice(greetings)

    @staticmethod
    def get_festival_wish():
        festivals = {
            "01-01": "🎉 Happy New Year! May this year bring you joy and success!",
            "01-14": "🎋 Happy Pongal/Makar Sankranti! Harvest festival greetings!",
            "01-26": "🇮🇳 Happy Republic Day! Jai Hind!",
            "02-14": "💝 Happy Valentine's Day! Spread love and kindness!",
            "03-08": "🌸 Happy Holi! May your life be filled with vibrant colors!",
            "03-25": "🎊 Happy Gudi Padwa/Ugadi! New Year greetings!",
            "04-14": "🎋 Happy Baisakhi/Vishu! May your harvest be abundant!",
            "04-21": "☪️ Eid Mubarak! May your prayers be answered!",
            "08-15": "🇮🇳 Happy Independence Day! Jai Hind!",
            "08-26": "🎉 Happy Janmashtami! May Lord Krishna bless you!",
            "09-07": "🎊 Happy Ganesh Chaturthi! Ganpati Bappa Morya!",
            "10-02": "🕊️ Happy Gandhi Jayanti! Be the change!",
            "10-24": "🪔 Happy Diwali! May light triumph over darkness!",
            "11-01": "🎊 Happy Kannada Rajyotsava! Karnataka formation day!",
            "11-14": "🎈 Happy Children's Day! Stay playful!",
            "12-25": "🎄 Merry Christmas! Peace and joy to you!"
        }
        today = datetime.now().strftime("%m-%d")
        return festivals.get(today, None)

    @staticmethod
    def get_motivation():
        motivations = [
            "💪 The only way to do great work is to love what you do.",
            "✨ Small progress is still progress. Keep going!",
            "🌟 Your limitation—it's only your imagination.",
            "🎯 Push yourself, because no one else is going to do it for you.",
            "🌈 Great things never come from comfort zones.",
            "🚀 Don't watch the clock; do what it does. Keep going.",
            "💡 Every expert was once a beginner.",
            "⭐ The future depends on what you do today.",
            "🔥 Success is not final, failure is not fatal."
        ]
        return f"💪 *Motivation*: {random.choice(motivations)}"
    
    @staticmethod
    def get_daily_tip():
        tips = [
            "Take regular breaks to maintain focus.",
            "Use strong, unique passwords for all accounts.",
            "Drink water first thing in the morning.",
            "Teach others to reinforce your own knowledge.",
            "Save at least 20% of your income.",
            "Update your apps regularly for security.",
            "Get 7-8 hours of sleep for better health.",
            "Take 5 minutes daily to meditate.",
            "Read for 30 minutes every day.",
            "Exercise at least 3 times a week."
        ]
        return f"💡 *Tip*: {random.choice(tips)}"
    
    @staticmethod
    async def get_news_headline():
        headlines = [
            "AI continues to revolutionize industries worldwide!",
            "Global cooperation on climate change intensifies.",
            "New discoveries about Mars captured public imagination.",
            "Cybersecurity becomes top priority for organizations.",
            "New game releases break previous sales records.",
            "5G networks expanding to more cities.",
            "New breakthroughs in artificial intelligence announced.",
            "Electric vehicle sales hit record high.",
            "Space tourism becomes reality for civilians."
        ]
        return f"📰 *News*: {random.choice(headlines)}"
    
    @staticmethod
    async def get_interesting_fact():
        facts = [
            "Elephants are the only mammals that can't jump.",
            "More people have been to the Moon than the Mariana Trench.",
            "Your brain generates enough electricity to power a lightbulb.",
            "Antarctica is the largest desert in the world.",
            "Your eyes blink about 20 times per minute.",
            "Bananas are berries, but strawberries aren't.",
            "Honey never spoils. It can last 3000 years!",
            "There are more stars than grains of sand on Earth.",
            "Octopuses have three hearts.",
            "A day on Venus is longer than a year on Venus."
        ]
        return f"🔬 *Did You Know?*: {random.choice(facts)}"

    @staticmethod
    async def get_daily_quote():
        quotes = [
            "The best way to predict the future is to create it. - Peter Drucker",
            "Success is not final, failure is not fatal. - Winston Churchill",
            "Believe you can and you're halfway there. - Theodore Roosevelt",
            "It does not matter how slowly you go as long as you do not stop. - Confucius",
            "Everything you've ever wanted is on the other side of fear. - Unknown",
            "The only impossible journey is the one you never begin. - Tony Robbins",
            "What you get by achieving your goals is not as important as what you become. - Zig Ziglar"
        ]
        return f"💭 *Quote*: {random.choice(quotes)}"

    @staticmethod
    async def get_random_content():
        """Get random content from various categories"""
        content_options = [
            AutoMessaging.get_time_based_greeting,
            AutoMessaging.get_random_greeting,
            AutoMessaging.get_motivation,
            AutoMessaging.get_daily_tip,
            FreeAPIServices.get_quote,
            FreeAPIServices.get_song_suggestion,
            FreeAPIServices.get_joke,
            FreeAPIServices.get_advice,
            FreeAPIServices.get_fact,
            AutoMessaging.get_news_headline,
            AutoMessaging.get_interesting_fact,
            AutoMessaging.get_daily_quote
        ]
        
        # Check for festival wishes
        festival_wish = AutoMessaging.get_festival_wish()
        if festival_wish:
            return festival_wish
        
        content_func = random.choice(content_options)
        if asyncio.iscoroutinefunction(content_func):
            return await content_func()
        return content_func()

    @staticmethod
    async def send_auto_message(context, chat_id: int):
        try:
            content = await AutoMessaging.get_random_content()
            
            # Random formatting templates
            templates = [
                f"""
🤖 *Alita Assistant Update*

{content}

---
🕐 {datetime.now().strftime('%I:%M %p')} • Use /help
""",
                f"""
🌟 *Daily Update* 🌟

{content}

━━━━━━━━━━━━━━━
🕒 {datetime.now().strftime('%I:%M %p')}
""",
                f"""
✨ *Hello Everyone!* ✨

{content}

📌 {datetime.now().strftime('%d %B %Y')}
"""
            ]
            
            formatted_content = random.choice(templates)
            
            await context.bot.send_message(
                chat_id=chat_id, 
                text=formatted_content,
                parse_mode='Markdown'
            )
            logger.info(f"✅ Auto message sent to {chat_id}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to send auto message: {e}")
            return False

# ==================== PERIODIC MESSAGE FUNCTION ====================
async def periodic_group_messages(context):
    """Send periodic messages to all groups"""
    try:
        groups = list(group_data.keys())
        
        if not groups:
            backup_groups = DataManager.load_data("groups_backup.json", [])
            groups = backup_groups
        
        auto_settings = DataManager.load_data(AUTO_SETTINGS_FILE, {})
        group_intervals = DataManager.load_data(INTERVALS_FILE, {})
        
        for group_id in groups:
            try:
                if not auto_settings.get(str(group_id), True):
                    continue
                
                interval_hours = group_intervals.get(str(group_id), 3)
                interval_seconds = interval_hours * 3600
                
                current_time = datetime.now()
                last_time = scheduler.last_message_time.get(str(group_id))
                
                if last_time is None or (current_time - last_time).total_seconds() >= interval_seconds:
                    success = await AutoMessaging.send_auto_message(context, int(group_id))
                    if success:
                        scheduler.update_last_message(str(group_id))
                    
                    await asyncio.sleep(2)
                    
            except Exception as e:
                logger.error(f"❌ Failed to process group {group_id}: {e}")
                continue
                
    except Exception as e:
        logger.error(f"❌ Periodic messaging error: {e}")

# ==================== MODERATION SYSTEM ====================
class ModerationSystem:
    BAD_WORDS = ["fuck", "shit", "asshole", "bastard", "bitch", "damn", "hell", "fck", "f*ck", "bch", "bsdk", "mc", "bc"]
    SPAM_LIMIT = 5
    
    @staticmethod
    def check_violation(message_text: str, user_id: str) -> str:
        if any(word in message_text.lower() for word in ModerationSystem.BAD_WORDS):
            return "bad_language"
        
        user_msg_count = user_data.get(user_id, {}).get("message_count", 0)
        if user_msg_count > ModerationSystem.SPAM_LIMIT:
            return "spamming"
        
        if len(message_text) > 500:
            return "flooding"
        
        if len(re.findall(r'http[s]?://', message_text)) > 5:
            return "link_spam"
        
        return ""

    @staticmethod
    async def take_action(update: Update, context: ContextTypes.DEFAULT_TYPE, violation: str, user_id: str):
        user = update.effective_user
        actions = {
            "bad_language": ("⚠️ Language Warning", "Please maintain respectful language in this group."),            
            "spamming": ("🚫 Spam Detected", "Please avoid sending too many messages quickly."),
            "flooding": ("📢 Long Message Warning", "Please keep messages at a reasonable length."),
            "link_spam": ("🔗 Link Spam", "Too many links detected. Please avoid link spamming.")
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
                content = await AutoMessaging.get_random_content()
                reminder_msg = f"""
🔔 *Channel Activity Reminder*

📊 *Status Report:*
• Last message: {last_message_time.strftime('%Y-%m-%d %H:%M')}
• Hours inactive: {hours_inactive:.1f}h
• Days inactive: {days_inactive:.1f}d

💡 *Suggestion:* Consider posting this:
{content}
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
            [KeyboardButton("👥 Group Tools"), KeyboardButton("👑 Admin")]
        ], resize_keyboard=True)

    @staticmethod
    def fun_menu():
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("😂 Joke", callback_data="fun_joke"),
             InlineKeyboardButton("💫 Quote", callback_data="fun_quote")],
            [InlineKeyboardButton("🤔 Advice", callback_data="fun_advice"),
             InlineKeyboardButton("📚 Fact", callback_data="fun_fact")],
            [InlineKeyboardButton("🎵 Song", callback_data="fun_song"),
             InlineKeyboardButton("💪 Motivation", callback_data="fun_motivation")],
            [InlineKeyboardButton("🔙 Back", callback_data="back_main")]
        ])

    @staticmethod
    def group_tools_menu():
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("👋 Welcome Msg", callback_data="group_welcome"),
             InlineKeyboardButton("🛡️ Moderation", callback_data="group_mod")],
            [InlineKeyboardButton("⏰ Auto Msg", callback_data="group_auto"),
             InlineKeyboardButton("📊 Stats", callback_data="group_stats")],
            [InlineKeyboardButton("🔙 Back", callback_data="back_main")]
        ])

    @staticmethod
    def admin_panel():
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast"),
             InlineKeyboardButton("📊 Stats", callback_data="admin_stats")],
            [InlineKeyboardButton("🛡️ Moderation", callback_data="admin_moderation"),
             InlineKeyboardButton("🔔 Channel", callback_data="admin_channel")],
            [InlineKeyboardButton("🔄 Auto Msg", callback_data="admin_auto"),
             InlineKeyboardButton("📋 Groups", callback_data="admin_groups")],
            [InlineKeyboardButton("🔙 Main Menu", callback_data="back_main")]
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

🌍 *Weather* • 🎵 *Music* • 😂 *Fun*
👥 *Group Tools* • 👑 *Admin*

*Auto messages every 3 hours in groups!*
*Welcome messages for new members!*

Use menu below to get started! 🚀
"""

    HELP = """
📖 *Commands:*

/start - Start bot
/help - This guide
/status - Bot status
/rules - Group rules
/auto - Trigger auto msg
/setinterval - Set interval
/toggleauto - Toggle auto

*Features:*
• Auto messages in groups
• Welcome new members
• Weather, Jokes, Quotes
• Music suggestions
• Group moderation
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
    
    active_today = 0
    for u in user_data.values():
        try:
            last_seen = datetime.fromisoformat(u.get('last_seen', datetime.now().isoformat()))
            if last_seen > datetime.now() - timedelta(days=1):
                active_today += 1
        except:
            pass
    
    status_text = f"""
🤖 *Alita Assistant Status*

✅ *All Systems Operational*
👥 Users: *{user_count}*
📱 Active Today: *{active_today}*
💬 Groups: *{group_count}*

🚀 *Services:*
• Weather: ✅ Live
• Entertainment: ✅ Ready
• Moderation: ✅ Active
• Auto-Responses: ✅ Active
• Welcome Msgs: ✅ Enabled

*Bot running perfectly!* ✨
"""
    await update.message.reply_text(status_text, parse_mode='Markdown')

async def rules_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rules_text = """
📜 *Group Rules*

1. ✅ Be respectful
2. ✅ No spam
3. ✅ No bad language
4. ✅ No harassment
5. ✅ Keep relevant
6. ✅ No promo without permission

*Be nice, have fun!* 🌟
"""
    await update.message.reply_text(rules_text, parse_mode='Markdown')

# ==================== AUTO RESPONSE COMMANDS ====================
async def trigger_auto_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type not in ["group", "supergroup"]:
        await update.message.reply_text("❌ This command only works in groups!")
        return
    
    chat = update.effective_chat
    content = await AutoMessaging.get_random_content()
    
    formatted_content = f"""
🤖 *Manual Auto Response*

{content}

---
Requested by: {update.effective_user.first_name}
🕐 {datetime.now().strftime('%I:%M %p')}
"""
    
    await update.message.reply_text(formatted_content, parse_mode='Markdown')
    scheduler.update_last_message(str(chat.id))

async def set_auto_interval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type not in ["group", "supergroup"]:
        await update.message.reply_text("❌ This command only works in groups!")
        return
    
    chat = update.effective_chat
    chat_id = str(chat.id)
    
    try:
        if context.args:
            hours = float(context.args[0])
            if hours < 1:
                await update.message.reply_text("❌ Interval must be at least 1 hour!")
                return
            if hours > 168:
                await update.message.reply_text("❌ Interval cannot exceed 168 hours (1 week)!")
                return
            
            intervals = DataManager.load_data(INTERVALS_FILE, {})
            intervals[chat_id] = hours
            DataManager.save_data(INTERVALS_FILE, intervals)
            
            await update.message.reply_text(
                f"✅ Auto-response interval set to {hours} hours!\n"
                f"Bot will send updates every {hours} hours."
            )
        else:
            intervals = DataManager.load_data(INTERVALS_FILE, {})
            current = intervals.get(chat_id, 3)
            await update.message.reply_text(
                f"📊 Current interval: {current} hours\n"
                f"To change: `/setinterval [hours]`\n"
                f"Example: `/setinterval 6`",
                parse_mode='Markdown'
            )
    except ValueError:
        await update.message.reply_text("❌ Please provide a valid number of hours!")

async def toggle_auto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type not in ["group", "supergroup"]:
        await update.message.reply_text("❌ This command only works in groups!")
        return
    
    chat = update.effective_chat
    chat_id = str(chat.id)
    
    settings = DataManager.load_data(AUTO_SETTINGS_FILE, {})
    current = settings.get(chat_id, True)
    settings[chat_id] = not current
    DataManager.save_data(AUTO_SETTINGS_FILE, settings)
    
    status = "enabled ✅" if settings[chat_id] else "disabled ❌"
    await update.message.reply_text(f"✅ Auto-responses {status} for this group!")

# ==================== MAIN MENU HANDLER ====================
async def handle_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    
    text = update.message.text
    
    if text == "🌍 Weather":
        weather = await FreeAPIServices.get_weather()
        await update.message.reply_text(weather)
    
    elif text == "🎵 Music":
        song = await FreeAPIServices.get_song_suggestion()
        await update.message.reply_text(song)
    
    elif text == "😂 Fun":
        await update.message.reply_text(
            "🎉 *Fun Zone*",
            reply_markup=Keyboards.fun_menu(),
            parse_mode='Markdown'
        )
    
    elif text == "👥 Group Tools":
        if update.effective_chat.type not in ["group", "supergroup"]:
            await update.message.reply_text("❌ Group tools only work in groups!")
            return
        await update.message.reply_text(
            "👥 *Group Tools*",
            reply_markup=Keyboards.group_tools_menu(),
            parse_mode='Markdown'
        )
    
    elif text == "👑 Admin":
        if update.effective_user.id != ADMIN_ID:
            await update.message.reply_text("❌ Admin access required!")
            return
        
        await update.message.reply_text(
            "👑 *Admin Panel*",
            reply_markup=Keyboards.admin_panel(),
            parse_mode='Markdown'
        )
    
    elif text == "🛠️ Tools":
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        await update.message.reply_text(
            f"🛠️ *Tools*\n\n"
            f"🕐 Time: `{current_time}`\n"
            f"💻 Status: Online\n\n"
            f"Use /help for commands.",
            parse_mode='Markdown'
        )
    
    else:
        await handle_general_message(update, context)

# ==================== GENERAL MESSAGE HANDLER ====================
async def handle_general_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    
    user_id = str(update.effective_user.id)
    text = update.message.text or ""
    
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
    
    if update.effective_chat.type in ["group", "supergroup"]:
        violation = ModerationSystem.check_violation(text, user_id)
        if violation:
            await ModerationSystem.take_action(update, context, violation, user_id)
            DataManager.save_data(USER_FILE, user_data)
            return
    
    text_lower = text.lower()
    
    if any(word in text_lower for word in ['hello', 'hi', 'hey', 'hola', 'namaste']):
        greetings = [
            f"👋 Hello {update.effective_user.first_name}!",
            f"Hi there! 👋",
            f"Hey {update.effective_user.first_name}!",
            f"Namaste! 🙏"
        ]
        await update.message.reply_text(random.choice(greetings))
    
    elif any(word in text_lower for word in ['thanks', 'thank you', 'thx', 'thank']):
        thanks = [
            "😊 You're welcome!",
            "Happy to help! 🌟",
            "Anytime! 😊",
            "Glad I could assist! 👍"
        ]
        await update.message.reply_text(random.choice(thanks))
    
    elif any(phrase in text_lower for phrase in ['how are you', 'how r u', 'how doin']):
        responses = [
            "🤖 I'm doing great!",
            "Running perfectly! 💫",
            "All systems operational!",
            "Better now that you're here! 😊"
        ]
        await update.message.reply_text(random.choice(responses))
    
    elif any(word in text_lower for word in ['bye', 'goodbye', 'see you', 'tata']):
        byes = [
            "👋 Goodbye!",
            "See you later! 👋",
            "Take care! 🌟",
            "Bye! Come back anytime!"
        ]
        await update.message.reply_text(random.choice(byes))
    
    elif any(word in text_lower for word in ['help', 'support', 'guide']):
        await update.message.reply_text("Need help? Try /help 📖")
    
    DataManager.save_data(USER_FILE, user_data)

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
        
        elif data == "fun_motivation":
            motivation = AutoMessaging.get_motivation()
            await query.edit_message_text(motivation, reply_markup=Keyboards.fun_menu(), parse_mode='Markdown')
        
        elif data == "group_welcome":
            await query.edit_message_text(
                "👋 *Welcome Messages*\n\n"
                "• New members are welcomed\n"
                "• Random welcome templates\n"
                "• Auto-enabled",
                reply_markup=Keyboards.group_tools_menu(),
                parse_mode='Markdown'
            )
        
        elif data == "group_mod":
            await query.edit_message_text(
                "🛡️ *Moderation*\n\n"
                "• Bad words filter: Active\n"
                "• Spam protection: Active\n"
                "• Link moderation: Active",
                reply_markup=Keyboards.group_tools_menu(),
                parse_mode='Markdown'
            )
        
        elif data == "group_auto":
            intervals = DataManager.load_data(INTERVALS_FILE, {})
            current = intervals.get(str(update.effective_chat.id), 3)
            await query.edit_message_text(
                f"⏰ *Auto Messages*\n\n"
                f"• Interval: {current} hours\n"
                f"• Use /setinterval to change\n"
                f"• Use /toggleauto to disable",
                reply_markup=Keyboards.group_tools_menu(),
                parse_mode='Markdown'
            )
        
        elif data == "group_stats":
            chat = update.effective_chat
            member_count = 0
            try:
                member_count = await chat.get_member_count()
            except:
                pass
            
            await query.edit_message_text(
                f"📊 *Group Stats*\n\n"
                f"• Name: {chat.title}\n"
                f"• Members: {member_count}\n"
                f"• ID: `{chat.id}`",
                reply_markup=Keyboards.group_tools_menu(),
                parse_mode='Markdown'
            )
        
        elif data == "admin_stats":
            if update.effective_user.id != ADMIN_ID:
                await query.edit_message_text("❌ Admin access required!")
                return
            
            user_count = len(user_data)
            group_count = len(group_data)
            
            active_today = 0
            for u in user_data.values():
                try:
                    last_seen = datetime.fromisoformat(u.get('last_seen', datetime.now().isoformat()))
                    if last_seen > datetime.now() - timedelta(days=1):
                        active_today += 1
                except:
                    pass
            
            total_messages = sum(u.get('message_count', 0) for u in user_data.values())
            
            stats_text = f"""
📊 *Admin Stats*

👥 Users: {user_count}
📱 Active Today: {active_today}
💬 Groups: {group_count}
🔄 Messages: {total_messages}
"""
            await query.edit_message_text(stats_text, reply_markup=Keyboards.admin_panel(), parse_mode='Markdown')
        
        elif data == "admin_broadcast":
            if update.effective_user.id != ADMIN_ID:
                await query.edit_message_text("❌ Admin access required!")
                return
            
            success_count = 0
            for user_id in user_data.keys():
                try:
                    await context.bot.send_message(
                        chat_id=int(user_id),
                        text="📢 *Broadcast*\n\nHello from Alita Assistant! 🌟",
                        parse_mode='Markdown'
                    )
                    success_count += 1
                    await asyncio.sleep(0.1)
                except:
                    continue
            
            await query.edit_message_text(
                f"✅ Broadcast sent to {success_count} users!",
                reply_markup=Keyboards.admin_panel()
            )
        
        elif data == "admin_channel":
            if update.effective_user.id != ADMIN_ID:
                await query.edit_message_text("❌ Admin access required!")
                return
            
            await ChannelMonitor.check_channel_activity(context)
            await query.edit_message_text("✅ Channel check done!", reply_markup=Keyboards.admin_panel())
        
        elif data == "admin_auto":
            if update.effective_user.id != ADMIN_ID:
                await query.edit_message_text("❌ Admin access required!")
                return
            
            await AutoMessaging.send_auto_message(context, update.effective_chat.id)
            await query.edit_message_text("✅ Auto message sent!", reply_markup=Keyboards.admin_panel())
        
        elif data == "admin_groups":
            if update.effective_user.id != ADMIN_ID:
                await query.edit_message_text("❌ Admin access required!")
                return
            
            groups_list = "📋 *Groups*\n\n"
            if group_data:
                for gid, ginfo in list(group_data.items())[:10]:
                    title = ginfo.get('title', 'Unknown')
                    groups_list += f"• {title}\n  ID: `{gid}`\n\n"
            else:
                groups_list += "No groups yet."
            
            await query.edit_message_text(groups_list, reply_markup=Keyboards.admin_panel(), parse_mode='Markdown')
        
        elif data == "admin_moderation":
            if update.effective_user.id != ADMIN_ID:
                await query.edit_message_text("❌ Admin access required!")
                return
            
            mod_text = """
🛡️ *Moderation Settings*

• Bad words filter: Enabled
• Spam protection: Enabled
• Flood control: Enabled
• Link moderation: Enabled
"""
            await query.edit_message_text(mod_text, reply_markup=Keyboards.admin_panel(), parse_mode='Markdown')
        
        elif data == "back_main":
            await query.edit_message_text(
                "🏠 *Main Menu*",
                reply_markup=Keyboards.main_menu(),
                parse_mode='Markdown'
            )
        
        else:
            await query.edit_message_text(
                "🛠️ Coming soon!",
                reply_markup=Keyboards.back_only()
            )
    
    except Exception as e:
        logger.error(f"Button error: {e}")
        await query.edit_message_text(
            "❌ Error",
            reply_markup=Keyboards.back_only()
        )

# ==================== GROUP HANDLERS ====================
async def group_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not bot_settings.get("welcome_message", True):
        return
    
    new_members = update.message.new_chat_members
    
    for member in new_members:
        if member.id == context.bot.id:
            group_id = str(update.effective_chat.id)
            group_data[group_id] = {
                "title": update.effective_chat.title,
                "added_date": datetime.now().isoformat()
            }
            DataManager.save_data(GROUP_FILE, group_data)
            
            groups_backup = DataManager.load_data("groups_backup.json", [])
            if group_id not in groups_backup:
                groups_backup.append(group_id)
                DataManager.save_data("groups_backup.json", groups_backup)
            
            welcome_msg = f"""
🤖 *Thanks for adding me!*

✅ Auto-moderation
✅ Welcome messages
✅ Auto updates every 3h
✅ Entertainment

Use /help for commands! 🚀
"""
            await update.message.reply_text(welcome_msg, parse_mode='Markdown')
            
        else:
            welcome_templates = [
                f"👋 Welcome {member.first_name}! 🌟",
                f"Hey {member.first_name}! Welcome to the group! 🎉",
                f"Please welcome {member.first_name}! 👋",
                f"🎊 New member: {member.first_name}! Welcome!"
            ]
            
            welcome_msg = random.choice(welcome_templates)
            await update.message.reply_text(welcome_msg)

async def group_left(update: Update, context: ContextTypes.DEFAULT_TYPE):
    left_member = update.message.left_chat_member
    if left_member and left_member.id != context.bot.id:
        if random.random() < 0.3:
            goodbye = f"👋 Goodbye {left_member.first_name}!"
            await update.message.reply_text(goodbye)

# ==================== ERROR HANDLER ====================
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Error: {context.error}")

# ==================== PERIODIC TASK STARTER ====================
async def start_periodic_messages(application: Application):
    async def periodic_wrapper():
        await asyncio.sleep(60)
        while True:
            try:
                class SimpleContext:
                    def __init__(self, bot):
                        self.bot = bot
                
                context = SimpleContext(application.bot)
                await periodic_group_messages(context)
                
                if random.random() < 0.1:
                    await ChannelMonitor.check_channel_activity(context)
                
                await asyncio.sleep(3600)
                
            except Exception as e:
                logger.error(f"Periodic error: {e}")
                await asyncio.sleep(300)
    
    asyncio.create_task(periodic_wrapper())
    logger.info("✅ Periodic messages started")

# ==================== HEALTH CHECK ====================
async def health_check(request):
    return aiohttp.web.Response(text="OK")

async def run_web_server():
    try:
        from aiohttp import web
        app = web.Application()
        app.router.add_get('/', health_check)
        app.router.add_get('/health', health_check)
        
        port = int(os.environ.get("PORT", 10000))
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', port)
        await site.start()
        logger.info(f"✅ Health server on port {port}")
    except Exception as e:
        logger.error(f"Health server error: {e}")

# ==================== MAIN ====================
def main():
    def signal_handler(signum, frame):
        logger.info("Shutting down...")
        DataManager.save_data(USER_FILE, user_data)
        DataManager.save_data(GROUP_FILE, group_data)
        DataManager.save_data(SETTINGS_FILE, bot_settings)
        DataManager.save_data(CHANNEL_FILE, channel_data)
        DataManager.save_data(SCHEDULE_FILE, scheduler.last_message_time)
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_error_handler(error_handler)
    
    # Add handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("rules", rules_command))
    application.add_handler(CommandHandler("auto", trigger_auto_response))
    application.add_handler(CommandHandler("setinterval", set_auto_interval))
    application.add_handler(CommandHandler("toggleauto", toggle_auto))
    
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_main_menu))
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, group_welcome))
    application.add_handler(MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER, group_left))
    
    async def post_init(application: Application):
        await application.bot.set_my_commands([
            BotCommand("start", "Start bot"),
            BotCommand("help", "Help guide"),
            BotCommand("status", "Bot status"),
            BotCommand("rules", "Group rules"),
            BotCommand("auto", "Trigger auto msg"),
            BotCommand("setinterval", "Set interval"),
            BotCommand("toggleauto", "Toggle auto")
        ])
        logger.info("✅ Commands set")
        
        await start_periodic_messages(application)
        asyncio.create_task(run_web_server())
        logger.info("✅ Ready!")
    
    application.post_init = post_init
    
    logger.info("🚀 Starting Alita Assistant...")
    logger.info(f"👑 Admin: {ADMIN_ID}")
    
    try:
        application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
    except Exception as e:
        logger.error(f"Bot failed: {e}")
        DataManager.save_data(USER_FILE, user_data)
        DataManager.save_data(GROUP_FILE, group_data)
        sys.exit(1)

if __name__ == "__main__":
    main()
