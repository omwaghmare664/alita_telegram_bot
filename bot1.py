from typing import Final, Dict, List, Optional
from telegram import (
    Update, 
    InlineKeyboardButton, 
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
    BotCommand,
    ChatPermissions
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
from collections import defaultdict

# ==================== CONFIGURATION ====================
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==================== TOKENS AND IDs ====================
BOT_TOKEN = "8168577329:AAFgYEHmIe-SDuRL3tqt6rx1MtAnJprSbRc"
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
WARNINGS_FILE = "warnings.json"

# Create empty files if they don't exist
for file in [USER_FILE, GROUP_FILE, SETTINGS_FILE, CHANNEL_FILE, SCHEDULE_FILE, INTERVALS_FILE, AUTO_SETTINGS_FILE, WARNINGS_FILE]:
    if not os.path.exists(file):
        DataManager.save_data(file, {})

user_data = DataManager.load_data(USER_FILE, {})
group_data = DataManager.load_data(GROUP_FILE, {})
warnings_data = DataManager.load_data(WARNINGS_FILE, {})
bot_settings = DataManager.load_data(SETTINGS_FILE, {
    "auto_reply": True,
    "welcome_message": True,
    "anti_spam": True,
    "auto_moderation": True,
    "auto_quote_interval": 10  # minutes
})
channel_data = DataManager.load_data(CHANNEL_FILE, {
    "last_message_time": datetime.now().isoformat()
})

# ==================== SCHEDULED MESSAGES SYSTEM ====================
class ScheduledMessages:
    def __init__(self):
        self.last_message_time = {}
        self.last_quote_time = {}
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
    
    def should_send_quote(self, chat_id: str, interval_minutes: int = 10) -> bool:
        """Check if enough time has passed to send another quote"""
        current_time = datetime.now()
        
        if chat_id not in self.last_quote_time:
            self.last_quote_time[chat_id] = current_time
            return True
        
        last_time = self.last_quote_time[chat_id]
        time_diff = (current_time - last_time).total_seconds()
        
        return time_diff >= interval_minutes * 60
    
    def update_last_message(self, chat_id: str):
        self.last_message_time[chat_id] = datetime.now()
        self.save_schedule_data()
    
    def update_last_quote(self, chat_id: str):
        self.last_quote_time[chat_id] = datetime.now()
        self.save_schedule_data()
    
    def save_schedule_data(self):
        schedule_data = {
            "messages": {},
            "quotes": {}
        }
        for chat_id, timestamp in self.last_message_time.items():
            schedule_data["messages"][chat_id] = timestamp.isoformat()
        for chat_id, timestamp in self.last_quote_time.items():
            schedule_data["quotes"][chat_id] = timestamp.isoformat()
        DataManager.save_data(SCHEDULE_FILE, schedule_data)
    
    def load_schedule_data(self):
        data = DataManager.load_data(SCHEDULE_FILE, {})
        messages = data.get("messages", {})
        quotes = data.get("quotes", {})
        
        for chat_id, timestamp_str in messages.items():
            try:
                self.last_message_time[chat_id] = datetime.fromisoformat(timestamp_str)
            except:
                pass
        
        for chat_id, timestamp_str in quotes.items():
            try:
                self.last_quote_time[chat_id] = datetime.fromisoformat(timestamp_str)
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
        return f"😂 *Joke of the moment:*\n{random.choice(jokes)}"

    @staticmethod
    async def get_quote() -> str:
        quotes = [
            ("The only way to do great work is to love what you do.", "Steve Jobs"),
            ("Innovation distinguishes between a leader and a follower.", "Steve Jobs"),
            ("Your time is limited, don't waste it living someone else's life.", "Steve Jobs"),
            ("The future belongs to those who believe in the beauty of their dreams.", "Eleanor Roosevelt"),
            ("Life is what happens when you're busy making other plans.", "John Lennon"),
            ("Success is not final, failure is not fatal: it is the courage to continue that counts.", "Winston Churchill"),
            ("Believe you can and you're halfway there.", "Theodore Roosevelt"),
            ("The best way to predict the future is to create it.", "Peter Drucker"),
            ("It does not matter how slowly you go as long as you do not stop.", "Confucius"),
            ("Everything you've ever wanted is on the other side of fear.", "Unknown"),
            ("The only impossible journey is the one you never begin.", "Tony Robbins"),
            ("What you get by achieving your goals is not as important as what you become.", "Zig Ziglar"),
            ("Happiness is not something ready-made. It comes from your own actions.", "Dalai Lama"),
            ("The purpose of our lives is to be happy.", "Dalai Lama"),
            ("Life is really simple, but we insist on making it complicated.", "Confucius")
        ]
        quote, author = random.choice(quotes)
        return f"💭 *Daily Inspiration*\n\n“{quote}”\n— {author}"

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
            "Exercise regularly for good health.",
            "Listen more than you speak.",
            "Forgive yourself for past mistakes.",
            "Celebrate small victories.",
            "Help others without expecting anything in return."
        ]
        return f"🤔 *Wisdom Drop*\n\n{random.choice(advice_list)}"

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
            "Humans share 60% of their DNA with bananas.",
            "Butterflies can taste with their feet.",
            "The world's oldest known living tree is over 5,000 years old."
        ]
        return f"📚 *Mind-Blowing Fact*\n\n{random.choice(facts)}"

    @staticmethod
    async def get_song_suggestion() -> str:
        songs = [
            ("Kesariya", "Brahmāstra"),
            ("Apna Bana Le", "Bhediya"), 
            ("Besharam Rang", "Pathaan"),
            ("Flowers", "Miley Cyrus"),
            ("Anti-Hero", "Taylor Swift"),
            ("As It Was", "Harry Styles"),
            ("Calm Down", "Rema"),
            ("Pasoori", "Coke Studio"),
            ("Kurchi Madathapetti", "Guntur Kaaram"),
            ("What Was I Made For", "Billie Eilish"),
            ("Vampire", "Olivia Rodrigo")
        ]
        song, artist = random.choice(songs)
        return f"🎵 *Music Recommendation*\n\n**{song}** by {artist}\n\nGive it a listen! 🎧"

# ==================== AUTO MESSAGING ====================
class AutoMessaging:
    @staticmethod
    def get_time_based_greeting():
        hour = datetime.now().hour
        if 5 <= hour < 12:
            return "🌅 *Good Morning!*\n\nRise and shine! Hope you have a wonderful day ahead filled with positivity and success!"
        elif 12 <= hour < 17:
            return "☀️ *Good Afternoon!*\n\nHope your day is going great! Keep up the amazing work!"
        elif 17 <= hour < 21:
            return "🌇 *Good Evening!*\n\nTime to relax and unwind. Hope you had a productive day!"
        else:
            return "🌙 *Good Night!*\n\nTime to rest and recharge. Sweet dreams and see you tomorrow!"

    @staticmethod
    def get_random_greeting():
        greetings = [
            "Hello everyone! 👋 Hope you're all having a fantastic day!",
            "Hi there, amazing people! 🌟 Stay awesome!",
            "Hey guys! 💫 Just dropping by to spread some positivity!",
            "Greetings everyone! ✨ How's your day going?",
            "Namaste! 🙏 Wishing you peace and happiness.",
            "Vanakkam! 🤝 Hope you're doing well!",
            "What's up everyone! 🚀 Let's make today great!"
        ]
        return random.choice(greetings)

    @staticmethod
    def get_festival_wish():
        festivals = {
            "01-01": "🎉 *Happy New Year!*\n\nMay 2024 bring you joy, success, and countless blessings! Wishing you and your family a fantastic year ahead!",
            "01-14": "🎋 *Happy Pongal/Makar Sankranti!*\n\nMay this harvest festival bring abundance and prosperity to your life!",
            "01-26": "🇮🇳 *Happy Republic Day!*\n\nLet's honor the spirit of freedom and democracy. Jai Hind! 🇮🇳",
            "02-14": "💝 *Happy Valentine's Day!*\n\nSpread love, kindness, and joy to everyone around you!",
            "03-08": "🌸 *Happy Holi!*\n\nMay your life be filled with the vibrant colors of joy, love, and happiness!",
            "03-25": "🎊 *Happy Gudi Padwa/Ugadi!*\n\nWishing you a prosperous New Year ahead!",
            "04-14": "🎋 *Happy Baisakhi/Vishu!*\n\nMay your harvest be abundant and your heart be full of gratitude!",
            "04-21": "☪️ *Eid Mubarak!*\n\nMay your prayers be answered and your heart be filled with peace!",
            "08-15": "🇮🇳 *Happy Independence Day!*\n\nCelebrate the spirit of freedom! Jai Hind! 🇮🇳",
            "08-26": "🎉 *Happy Janmashtami!*\n\nMay Lord Krishna bless you with love, wisdom, and prosperity!",
            "09-07": "🎊 *Happy Ganesh Chaturthi!*\n\nGanpati Bappa Morya! May Lord Ganesha remove all obstacles from your path!",
            "10-02": "🕊️ *Happy Gandhi Jayanti!*\n\nLet's follow the path of truth and non-violence. Be the change!",
            "10-24": "🪔 *Happy Diwali!*\n\nMay the festival of lights bring brightness, joy, and prosperity to your life!",
            "11-01": "🎊 *Happy Kannada Rajyotsava!*\n\nCelebrating the rich culture of Karnataka!",
            "11-14": "🎈 *Happy Children's Day!*\n\nStay playful, curious, and young at heart!",
            "12-25": "🎄 *Merry Christmas!*\n\nPeace, love, and joy to you and your family! 🎅"
        }
        today = datetime.now().strftime("%m-%d")
        wish = festivals.get(today)
        if wish:
            return f"🎊 *Festival Special* 🎊\n\n{wish}"
        return None

    @staticmethod
    def get_motivation():
        motivations = [
            "The only way to do great work is to love what you do. Keep pushing forward!",
            "Small progress is still progress. Every step counts on your journey!",
            "Your limitation—it's only your imagination. Dream bigger!",
            "Push yourself, because no one else is going to do it for you.",
            "Great things never come from comfort zones. Step out today!",
            "Don't watch the clock; do what it does. Keep going.",
            "Every expert was once a beginner. Keep learning!",
            "The future depends on what you do today. Make it count!",
            "Success is not final, failure is not fatal. Keep going!",
            "Your only limit is your mind. Believe you can!"
        ]
        return f"💪 *Daily Motivation*\n\n{random.choice(motivations)}"
    
    @staticmethod
    def get_daily_tip():
        tips = [
            "Take regular breaks to maintain focus and productivity.",
            "Use strong, unique passwords for all your accounts.",
            "Drink water first thing in the morning to kickstart your metabolism.",
            "Teach others to reinforce your own knowledge and understanding.",
            "Save at least 20% of your income for a secure future.",
            "Update your apps regularly for security and new features.",
            "Get 7-8 hours of sleep for better health and cognitive function.",
            "Take 5 minutes daily to meditate and clear your mind.",
            "Read for 30 minutes every day to expand your knowledge.",
            "Exercise at least 3 times a week for physical and mental health.",
            "Practice gratitude by noting three good things daily.",
            "Limit screen time before bed for better sleep quality."
        ]
        return f"💡 *Pro Tip*\n\n{random.choice(tips)}"
    
    @staticmethod
    async def get_news_headline():
        headlines = [
            "AI continues to revolutionize industries worldwide with new breakthroughs!",
            "Global cooperation on climate change intensifies as world leaders meet.",
            "New discoveries about Mars reveal exciting possibilities for human colonization.",
            "Cybersecurity becomes top priority as digital threats evolve.",
            "Space tourism becomes reality as more civilians experience space travel.",
            "Breakthrough in renewable energy promises cleaner future.",
            "Scientists make progress in cancer research with new treatment.",
            "Electric vehicle sales hit record high as prices become more affordable."
        ]
        return f"📰 *Trending Now*\n\n{random.choice(headlines)}"
    
    @staticmethod
    async def get_interesting_fact():
        facts = [
            "Elephants are the only mammals that can't jump.",
            "More people have been to the Moon than the deepest part of the ocean.",
            "Your brain generates enough electricity to power a small lightbulb.",
            "Antarctica is actually the largest desert in the world.",
            "Your eyes blink about 20 times per minute, that's millions per year!",
            "Bananas are technically berries, but strawberries aren't.",
            "Honey never spoils. It can last for thousands of years!",
            "There are more stars in space than grains of sand on all Earth's beaches.",
            "Octopuses have three hearts and blue blood.",
            "A day on Venus is longer than a year on Venus."
        ]
        return f"🔬 *Did You Know?*\n\n{random.choice(facts)}"

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
            AutoMessaging.get_interesting_fact
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
━━━━━━━━━━━━━━━━━━━━━
🤖 *Alita Assistant* 🤖
━━━━━━━━━━━━━━━━━━━━━

{content}

━━━━━━━━━━━━━━━━━━━━━
🕐 {datetime.now().strftime('%I:%M %p • %d %b %Y')}
━━━━━━━━━━━━━━━━━━━━━
""",
                f"""
🌟 *Community Update* 🌟

{content}

━━━━━━━━━━━━━━━
💫 Use /help for commands
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

    @staticmethod
    async def send_quote_message(context, chat_id: int):
        """Send only a quote"""
        try:
            quote = await FreeAPIServices.get_quote()
            
            formatted_quote = f"""
💭 *Thought of the Moment* 💭

{quote}

━━━━━━━━━━━━━━━
✨ Stay inspired!
"""
            
            await context.bot.send_message(
                chat_id=chat_id,
                text=formatted_quote,
                parse_mode='Markdown'
            )
            logger.info(f"✅ Quote sent to {chat_id}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to send quote: {e}")
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
                
                # Regular auto messages every 3 hours
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

async def periodic_quotes(context):
    """Send quotes every 10 minutes to all groups"""
    try:
        groups = list(group_data.keys())
        
        if not groups:
            backup_groups = DataManager.load_data("groups_backup.json", [])
            groups = backup_groups
        
        auto_settings = DataManager.load_data(AUTO_SETTINGS_FILE, {})
        quote_interval = bot_settings.get("auto_quote_interval", 10)
        
        for group_id in groups:
            try:
                if not auto_settings.get(str(group_id), True):
                    continue
                
                # Check if we should send a quote
                if scheduler.should_send_quote(str(group_id), quote_interval):
                    success = await AutoMessaging.send_quote_message(context, int(group_id))
                    if success:
                        scheduler.update_last_quote(str(group_id))
                    
                    await asyncio.sleep(2)
                    
            except Exception as e:
                logger.error(f"❌ Failed to send quote to {group_id}: {e}")
                continue
                
    except Exception as e:
        logger.error(f"❌ Periodic quotes error: {e}")

# ==================== ADVANCED MODERATION SYSTEM ====================
class ModerationSystem:
    BAD_WORDS = [
        "fuck", "shit", "asshole", "bastard", "bitch", "damn", "hell", 
        "fck", "f*ck", "bch", "bsdk", "mc", "bc", "motherfucker", 
        "dick", "pussy", "cunt", "whore", "slut", "nigger", "faggot"
    ]
    
    SPAM_LIMIT = 5  # messages
    SPAM_WINDOW = 10  # seconds
    WARN_LIMIT = 3  # warnings before action
    
    def __init__(self):
        self.user_message_count = defaultdict(list)  # Track message timestamps
        self.user_warnings = defaultdict(int)  # Track warning count
    
    def check_violation(self, message_text: str, user_id: str, chat_id: str) -> dict:
        """Check for violations and return details"""
        violations = []
        
        # Check bad words
        for word in self.BAD_WORDS:
            if word in message_text.lower():
                violations.append({
                    "type": "bad_language",
                    "word": word,
                    "severity": 2
                })
                break
        
        # Check spam
        now = datetime.now()
        self.user_message_count[user_id].append(now)
        # Keep only messages from last minute
        self.user_message_count[user_id] = [
            t for t in self.user_message_count[user_id] 
            if (now - t).total_seconds() < 60
        ]
        
        if len(self.user_message_count[user_id]) > self.SPAM_LIMIT:
            violations.append({
                "type": "spamming",
                "count": len(self.user_message_count[user_id]),
                "severity": 3
            })
        
        # Check message length
        if len(message_text) > 1000:
            violations.append({
                "type": "flooding",
                "length": len(message_text),
                "severity": 1
            })
        
        # Check links
        links = re.findall(r'http[s]?://', message_text)
        if len(links) > 3:
            violations.append({
                "type": "link_spam",
                "count": len(links),
                "severity": 2
            })
        
        # Check for excessive caps (SHOUTING)
        if len(message_text) > 50:
            caps_ratio = sum(1 for c in message_text if c.isupper()) / len(message_text)
            if caps_ratio > 0.7:
                violations.append({
                    "type": "excessive_caps",
                    "ratio": caps_ratio,
                    "severity": 1
                })
        
        return violations[0] if violations else None
    
    async def take_action(self, update: Update, context: ContextTypes.DEFAULT_TYPE, violation: dict, user_id: str):
        """Take appropriate action based on violation"""
        user = update.effective_user
        chat = update.effective_chat
        violation_type = violation["type"]
        
        # Increment warnings
        warning_key = f"{chat.id}:{user_id}"
        self.user_warnings[warning_key] += 1
        warning_count = self.user_warnings[warning_key]
        
        # Save warnings
        warnings_data[warning_key] = {
            "user_id": user_id,
            "chat_id": chat.id,
            "warnings": warning_count,
            "last_violation": violation_type,
            "timestamp": datetime.now().isoformat()
        }
        DataManager.save_data(WARNINGS_FILE, warnings_data)
        
        # Action templates
        actions = {
            "bad_language": {
                "message": f"⚠️ *Language Warning*\nUser: {user.first_name}\nReason: Inappropriate language detected.\nWarning: {warning_count}/{self.WARN_LIMIT}",
                "severity": 2
            },
            "spamming": {
                "message": f"🚫 *Spam Detected*\nUser: {user.first_name}\nReason: Too many messages in short time.\nWarning: {warning_count}/{self.WARN_LIMIT}",
                "severity": 3
            },
            "flooding": {
                "message": f"📢 *Long Message Warning*\nUser: {user.first_name}\nReason: Message too long (1000+ chars).\nWarning: {warning_count}/{self.WARN_LIMIT}",
                "severity": 1
            },
            "link_spam": {
                "message": f"🔗 *Link Spam*\nUser: {user.first_name}\nReason: Too many links detected.\nWarning: {warning_count}/{self.WARN_LIMIT}",
                "severity": 2
            },
            "excessive_caps": {
                "message": f"🔊 *Excessive Caps Warning*\nUser: {user.first_name}\nReason: Please don't SHOUT.\nWarning: {warning_count}/{self.WARN_LIMIT}",
                "severity": 1
            }
        }
        
        action = actions.get(violation_type, {
            "message": f"⚠️ *Rule Violation*\nUser: {user.first_name}\nWarning: {warning_count}/{self.WARN_LIMIT}",
            "severity": 1
        })
        
        try:
            # Send warning message
            warning_msg = f"{action['message']}\n\n*Please follow group rules.*"
            await update.message.reply_text(warning_msg, parse_mode='Markdown')
            
            # Delete violating message for severe violations
            if action['severity'] >= 2:
                try:
                    await update.message.delete()
                    logger.info(f"🗑️ Deleted violating message from {user_id}")
                except Exception as e:
                    logger.error(f"❌ Could not delete message: {e}")
            
            # Take escalated action based on warning count
            if warning_count >= self.WARN_LIMIT:
                await self.escalate_action(update, context, user_id, warning_count)
            
            logger.info(f"🛡️ Moderation action: {violation_type} for user {user_id} (warning {warning_count})")
            
        except Exception as e:
            logger.error(f"❌ Moderation action failed: {e}")
    
    async def escalate_action(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: str, warning_count: int):
        """Escalate action for repeat offenders"""
        user = update.effective_user
        chat = update.effective_chat
        
        try:
            if warning_count == self.WARN_LIMIT:
                # Mute for 1 hour
                permissions = ChatPermissions(
                    can_send_messages=False,
                    can_send_media_messages=False,
                    can_send_polls=False,
                    can_send_other_messages=False,
                    can_add_web_page_previews=False,
                    can_change_info=False,
                    can_invite_users=False,
                    can_pin_messages=False
                )
                
                until_date = datetime.now() + timedelta(hours=1)
                await context.bot.restrict_chat_member(
                    chat_id=chat.id,
                    user_id=user.id,
                    permissions=permissions,
                    until_date=until_date
                )
                
                mute_msg = f"""
🔇 *User Muted*

User: {user.first_name}
Duration: 1 hour
Reason: Reached {self.WARN_LIMIT} warnings

Please review group rules before participating again.
"""
                await context.bot.send_message(chat_id=chat.id, text=mute_msg, parse_mode='Markdown')
                logger.info(f"🔇 Muted user {user_id} for 1 hour")
                
            elif warning_count == self.WARN_LIMIT + 1:
                # Mute for 24 hours
                permissions = ChatPermissions(
                    can_send_messages=False,
                    can_send_media_messages=False,
                    can_send_polls=False,
                    can_send_other_messages=False,
                    can_add_web_page_previews=False,
                    can_change_info=False,
                    can_invite_users=False,
                    can_pin_messages=False
                )
                
                until_date = datetime.now() + timedelta(hours=24)
                await context.bot.restrict_chat_member(
                    chat_id=chat.id,
                    user_id=user.id,
                    permissions=permissions,
                    until_date=until_date
                )
                
                mute_msg = f"""
🔇 *User Muted (Extended)*

User: {user.first_name}
Duration: 24 hours
Reason: Continued violations

Repeated violations may lead to ban.
"""
                await context.bot.send_message(chat_id=chat.id, text=mute_msg, parse_mode='Markdown')
                logger.info(f"🔇 Muted user {user_id} for 24 hours")
                
            elif warning_count >= self.WARN_LIMIT + 2:
                # Ban user
                await context.bot.ban_chat_member(chat_id=chat.id, user_id=user.id)
                
                ban_msg = f"""
🚫 *User Banned*

User: {user.first_name} has been banned.
Reason: Persistent rule violations after multiple warnings.

This action is irreversible by the bot.
"""
                await context.bot.send_message(chat_id=chat.id, text=ban_msg, parse_mode='Markdown')
                logger.info(f"🚫 Banned user {user_id}")
                
                # Reset warnings after ban
                warning_key = f"{chat.id}:{user_id}"
                self.user_warnings[warning_key] = 0
                if warning_key in warnings_data:
                    del warnings_data[warning_key]
                    DataManager.save_data(WARNINGS_FILE, warnings_data)
                    
        except Exception as e:
            logger.error(f"❌ Escalation action failed: {e}")

# Initialize moderation system
mod_system = ModerationSystem()

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

💡 *Suggested Content:*
{content}

━━━━━━━━━━━━━━━
_Keep your community engaged!_
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
            [InlineKeyboardButton("🚫 Banned Users", callback_data="group_bans"),
             InlineKeyboardButton("⚠️ Warnings", callback_data="group_warnings")],
            [InlineKeyboardButton("🔙 Back", callback_data="back_main")]
        ])

    @staticmethod
    def admin_panel():
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast"),
             InlineKeyboardButton("📊 Stats", callback_data="admin_stats")],
            [InlineKeyboardButton("🛡️ Mod Settings", callback_data="admin_moderation"),
             InlineKeyboardButton("🔔 Channel", callback_data="admin_channel")],
            [InlineKeyboardButton("🔄 Auto Msg", callback_data="admin_auto"),
             InlineKeyboardButton("📋 Groups", callback_data="admin_groups")],
            [InlineKeyboardButton("🚫 Ban List", callback_data="admin_bans"),
             InlineKeyboardButton("⚠️ All Warnings", callback_data="admin_warnings")],
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

━━━━━━━━━━━━━━━━━━━━━
🌍 *Weather* • 🎵 *Music* • 😂 *Fun*
👥 *Group Tools* • 👑 *Admin*
━━━━━━━━━━━━━━━━━━━━━

🎯 *What I Can Do:*
• Auto quotes every 10 minutes
• Auto messages every 3 hours
• Welcome new members warmly
• Moderate bad language & spam
• Ban repeat offenders
• Entertainment & facts

Use menu below to get started! 🚀
"""

    HELP = """
📖 *Commands Guide*

━━━━━━━━━━━━━━━━━━━━━
*Basic Commands:*
/start - Start the bot
/help - Show this guide
/status - Bot status
/rules - Group rules

*Group Commands:*
/auto - Trigger auto msg
/setinterval - Set interval
/toggleauto - Toggle auto
/warnings - Check warnings
/mywarns - Your warnings

*Admin Commands:*
/ban @user - Ban user
/unban @user - Unban user
/mute @user - Mute user
/warn @user - Warn user
/clearwarns @user - Clear warns
━━━━━━━━━━━━━━━━━━━━━

✨ *Features:*
• Auto quotes every 10 min
• Welcome new members
• Weather, Jokes, Quotes
• Music suggestions
• Advanced moderation
• Ban repeat offenders
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
    
    total_warnings = len(warnings_data)
    
    status_text = f"""
🤖 *Alita Assistant Status*

━━━━━━━━━━━━━━━━━━━━━
✅ *All Systems Operational*
━━━━━━━━━━━━━━━━━━━━━

👥 Total Users: *{user_count}*
📱 Active Today: *{active_today}*
💬 Groups: *{group_count}*
⚠️ Total Warnings: *{total_warnings}*

🚀 *Services:*
• Weather: ✅ Live
• Entertainment: ✅ Ready
• Moderation: ✅ Active
• Auto Quotes: ✅ Every 10min
• Auto Messages: ✅ Every 3h
• Welcome Msgs: ✅ Enabled
• Ban System: ✅ Active

━━━━━━━━━━━━━━━━━━━━━
✨ *Bot running perfectly!*
"""
    await update.message.reply_text(status_text, parse_mode='Markdown')

async def rules_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rules_text = """
📜 *Group Rules*

━━━━━━━━━━━━━━━━━━━━━
1. ✅ *Be respectful* to all members
2. ✅ *No spam* or flooding
3. ✅ *No bad language* or profanity
4. ✅ *No harassment* or bullying
5. ✅ *Keep discussions* relevant
6. ✅ *No promotions* without permission
7. ✅ *No NSFW* content
8. ✅ *No hate speech* of any kind
━━━━━━━━━━━━━━━━━━━━━

⚠️ *Enforcement:*
• 1st-2nd warning: Verbal warning
• 3rd warning: Muted for 1 hour
• 4th warning: Muted for 24 hours
• 5th warning: Banned permanently

━━━━━━━━━━━━━━━━━━━━━
*Be nice, have fun!* 🌟
"""
    await update.message.reply_text(rules_text, parse_mode='Markdown')

async def my_warnings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check your own warnings"""
    user = update.effective_user
    chat = update.effective_chat
    
    if chat.type not in ["group", "supergroup"]:
        await update.message.reply_text("❌ This command only works in groups!")
        return
    
    warning_key = f"{chat.id}:{user.id}"
    warning_count = mod_system.user_warnings.get(warning_key, 0)
    
    warning_info = warnings_data.get(warning_key, {})
    last_violation = warning_info.get("last_violation", "None")
    last_time = warning_info.get("timestamp", "Unknown")
    
    if last_time != "Unknown":
        try:
            last_time = datetime.fromisoformat(last_time).strftime('%Y-%m-%d %H:%M')
        except:
            pass
    
    msg = f"""
⚠️ *Your Warnings*

━━━━━━━━━━━━━━━━━━━━━
User: {user.first_name}
Current Warnings: {warning_count}/{ModerationSystem.WARN_LIMIT + 2}

Last Violation: {last_violation}
Last Warning: {last_time}
━━━━━━━━━━━━━━━━━━━━━

*Warning Levels:*
• {ModerationSystem.WARN_LIMIT} warnings: Mute 1h
• {ModerationSystem.WARN_LIMIT+1} warnings: Mute 24h
• {ModerationSystem.WARN_LIMIT+2} warnings: Ban

Please follow rules to avoid action.
"""
    await update.message.reply_text(msg, parse_mode='Markdown')

async def warnings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command to check warnings"""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Admin access required!")
        return
    
    chat = update.effective_chat
    
    if chat.type not in ["group", "supergroup"]:
        await update.message.reply_text("❌ This command only works in groups!")
        return
    
    # Get all warnings for this chat
    chat_warnings = []
    for key, data in warnings_data.items():
        if key.startswith(f"{chat.id}:"):
            user_id = key.split(":")[1]
            try:
                user = await context.bot.get_chat_member(chat.id, int(user_id))
                username = user.user.username or user.user.first_name
                chat_warnings.append({
                    "user": username,
                    "warnings": data.get("warnings", 0),
                    "last": data.get("last_violation", "Unknown")
                })
            except:
                continue
    
    if not chat_warnings:
        await update.message.reply_text("✅ No warnings in this group!")
        return
    
    msg = "⚠️ *Group Warnings*\n\n"
    for w in sorted(chat_warnings, key=lambda x: x["warnings"], reverse=True)[:10]:
        msg += f"• {w['user']}: {w['warnings']} warnings (last: {w['last']})\n"
    
    await update.message.reply_text(msg, parse_mode='Markdown')

async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ban a user"""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Admin access required!")
        return
    
    chat = update.effective_chat
    
    if chat.type not in ["group", "supergroup"]:
        await update.message.reply_text("❌ This command only works in groups!")
        return
    
    if not context.args:
        await update.message.reply_text("Usage: /ban @username")
        return
    
    try:
        username = context.args[0].replace("@", "")
        # Find user by username
        user_to_ban = None
        
        async for member in chat.get_members():
            if member.user.username and member.user.username.lower() == username.lower():
                user_to_ban = member.user
                break
        
        if not user_to_ban:
            await update.message.reply_text("❌ User not found!")
            return
        
        await context.bot.ban_chat_member(chat_id=chat.id, user_id=user_to_ban.id)
        
        msg = f"""
🚫 *User Banned*

User: {user_to_ban.first_name} (@{username})
Banned by: {update.effective_user.first_name}

This action is permanent.
"""
        await update.message.reply_text(msg, parse_mode='Markdown')
        
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Unban a user"""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Admin access required!")
        return
    
    chat = update.effective_chat
    
    if chat.type not in ["group", "supergroup"]:
        await update.message.reply_text("❌ This command only works in groups!")
        return
    
    if not context.args:
        await update.message.reply_text("Usage: /unban @username")
        return
    
    try:
        username = context.args[0].replace("@", "")
        # You'll need the user ID to unban - this is simplified
        await update.message.reply_text("❌ Unban requires user ID. Please check banned list first.")
        
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def mute_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mute a user"""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Admin access required!")
        return
    
    chat = update.effective_chat
    
    if chat.type not in ["group", "supergroup"]:
        await update.message.reply_text("❌ This command only works in groups!")
        return
    
    if not context.args:
        await update.message.reply_text("Usage: /mute @username [hours]")
        return
    
    try:
        username = context.args[0].replace("@", "")
        hours = int(context.args[1]) if len(context.args) > 1 else 1
        
        # Find user
        user_to_mute = None
        async for member in chat.get_members():
            if member.user.username and member.user.username.lower() == username.lower():
                user_to_mute = member.user
                break
        
        if not user_to_mute:
            await update.message.reply_text("❌ User not found!")
            return
        
        permissions = ChatPermissions(
            can_send_messages=False,
            can_send_media_messages=False,
            can_send_polls=False,
            can_send_other_messages=False,
            can_add_web_page_previews=False
        )
        
        until_date = datetime.now() + timedelta(hours=hours)
        await context.bot.restrict_chat_member(
            chat_id=chat.id,
            user_id=user_to_mute.id,
            permissions=permissions,
            until_date=until_date
        )
        
        msg = f"""
🔇 *User Muted*

User: {user_to_mute.first_name} (@{username})
Duration: {hours} hour(s)
Muted by: {update.effective_user.first_name}
"""
        await update.message.reply_text(msg, parse_mode='Markdown')
        
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

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

━━━━━━━━━━━━━━━
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
        await update.message.reply_text(weather, parse_mode='Markdown')
    
    elif text == "🎵 Music":
        song = await FreeAPIServices.get_song_suggestion()
        await update.message.reply_text(song, parse_mode='Markdown')
    
    elif text == "😂 Fun":
        await update.message.reply_text(
            "🎉 *Fun Zone* - Choose your entertainment!",
            reply_markup=Keyboards.fun_menu(),
            parse_mode='Markdown'
        )
    
    elif text == "👥 Group Tools":
        if update.effective_chat.type not in ["group", "supergroup"]:
            await update.message.reply_text("❌ Group tools only work in groups!")
            return
        await update.message.reply_text(
            "👥 *Group Management Tools*",
            reply_markup=Keyboards.group_tools_menu(),
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
        uptime = "24/7 Active"
        await update.message.reply_text(
            f"🛠️ *Tools & Utilities*\n\n"
            f"🕐 Current Time: `{current_time}`\n"
            f"📊 Uptime: {uptime}\n"
            f"💻 Status: Online\n\n"
            f"Use /help for more commands.",
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
    
    # Advanced moderation in groups
    if update.effective_chat.type in ["group", "supergroup"]:
        violation = mod_system.check_violation(text, user_id, str(update.effective_chat.id))
        if violation:
            await mod_system.take_action(update, context, violation, user_id)
            DataManager.save_data(USER_FILE, user_data)
            return
    
    # Smart replies
    text_lower = text.lower()
    
    if any(word in text_lower for word in ['hello', 'hi', 'hey', 'hola', 'namaste', 'vanakkam']):
        greetings = [
            f"👋 Hello {update.effective_user.first_name}! How can I help?",
            f"Hi there {update.effective_user.first_name}! 👋",
            f"Hey {update.effective_user.first_name}! What's up?",
            f"Namaste {update.effective_user.first_name}! 🙏",
            f"Greetings {update.effective_user.first_name}! 🌟"
        ]
        await update.message.reply_text(random.choice(greetings))
    
    elif any(word in text_lower for word in ['thanks', 'thank you', 'thx', 'thank', 'ty']):
        thanks = [
            "😊 You're welcome!",
            "Happy to help! 🌟",
            "Anytime! 😊",
            "Glad I could assist! 👍",
            "My pleasure! 💫"
        ]
        await update.message.reply_text(random.choice(thanks))
    
    elif any(phrase in text_lower for phrase in ['how are you', 'how r u', 'how doin', 'how are u']):
        responses = [
            "🤖 I'm doing great! Thanks for asking!",
            "Running perfectly! How about you? 💫",
            "All systems operational! Hope you're well too!",
            "Better now that you're here! 😊",
            "I'm awesome, thanks for checking! 🚀"
        ]
        await update.message.reply_text(random.choice(responses))
    
    elif any(word in text_lower for word in ['bye', 'goodbye', 'see you', 'tata', 'cya']):
        byes = [
            "👋 Goodbye! Come back anytime!",
            "See you later! Take care! 👋",
            "Take care! Hope to see you soon! 🌟",
            "Bye! Have a great day!",
            "Until next time! 👋"
        ]
        await update.message.reply_text(random.choice(byes))
    
    elif any(word in text_lower for word in ['help', 'support', 'guide', 'commands']):
        await update.message.reply_text("Need help? Try /help for the full command list! 📖")
    
    elif any(word in text_lower for word in ['joke', 'jokes', 'funny']):
        joke = await FreeAPIServices.get_joke()
        await update.message.reply_text(joke, parse_mode='Markdown')
    
    elif any(word in text_lower for word in ['quote', 'quotes', 'inspire']):
        quote = await FreeAPIServices.get_quote()
        await update.message.reply_text(quote, parse_mode='Markdown')
    
    elif any(word in text_lower for word in ['fact', 'facts']):
        fact = await FreeAPIServices.get_fact()
        await update.message.reply_text(fact, parse_mode='Markdown')
    
    DataManager.save_data(USER_FILE, user_data)

# ==================== BUTTON HANDLER ====================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    try:
        # Fun menu buttons
        if data == "fun_joke":
            joke = await FreeAPIServices.get_joke()
            await query.edit_message_text(joke, reply_markup=Keyboards.fun_menu(), parse_mode='Markdown')
        
        elif data == "fun_quote":
            quote = await FreeAPIServices.get_quote()
            await query.edit_message_text(quote, reply_markup=Keyboards.fun_menu(), parse_mode='Markdown')
        
        elif data == "fun_advice":
            advice = await FreeAPIServices.get_advice()
            await query.edit_message_text(advice, reply_markup=Keyboards.fun_menu(), parse_mode='Markdown')
        
        elif data == "fun_fact":
            fact = await FreeAPIServices.get_fact()
            await query.edit_message_text(fact, reply_markup=Keyboards.fun_menu(), parse_mode='Markdown')
        
        elif data == "fun_song":
            song = await FreeAPIServices.get_song_suggestion()
            await query.edit_message_text(song, reply_markup=Keyboards.fun_menu(), parse_mode='Markdown')
        
        elif data == "fun_motivation":
            motivation = AutoMessaging.get_motivation()
            await query.edit_message_text(motivation, reply_markup=Keyboards.fun_menu(), parse_mode='Markdown')
        
        # Group tools menu
        elif data == "group_welcome":
            await query.edit_message_text(
                "👋 *Welcome Message Settings*\n\n"
                "• New members are automatically welcomed\n"
                "• Random welcome templates used\n"
                "• Status: ✅ Enabled\n\n"
                "To disable: Ask admin to modify settings",
                reply_markup=Keyboards.group_tools_menu(),
                parse_mode='Markdown'
            )
        
        elif data == "group_mod":
            await query.edit_message_text(
                "🛡️ *Moderation Settings*\n\n"
                "• Bad words filter: ✅ Active\n"
                "• Spam protection: ✅ Active\n"
                "• Flood control: ✅ Active\n"
                "• Link moderation: ✅ Active\n"
                "• Caps lock control: ✅ Active\n\n"
                f"• Warning limit: {ModerationSystem.WARN_LIMIT} before action\n\n"
                "⚠️ After 3 warnings: Mute 1h\n"
                "⚠️ After 4 warnings: Mute 24h\n"
                "⚠️ After 5 warnings: Ban",
                reply_markup=Keyboards.group_tools_menu(),
                parse_mode='Markdown'
            )
        
        elif data == "group_auto":
            intervals = DataManager.load_data(INTERVALS_FILE, {})
            current = intervals.get(str(update.effective_chat.id), 3)
            quote_interval = bot_settings.get("auto_quote_interval", 10)
            
            await query.edit_message_text(
                f"⏰ *Auto Message Settings*\n\n"
                f"• Regular messages: Every {current} hours\n"
                f"• Inspirational quotes: Every {quote_interval} minutes\n"
                f"• Use /setinterval to change hours\n"
                f"• Use /toggleauto to enable/disable\n\n"
                f"Status: ✅ Active",
                reply_markup=Keyboards.group_tools_menu(),
                parse_mode='Markdown'
            )
        
        elif data == "group_stats":
            chat = update.effective_chat
            member_count = 0
            active_today = 0
            
            try:
                member_count = await chat.get_member_count()
                
                # Count warnings in this group
                group_warnings = 0
                for key in warnings_data:
                    if key.startswith(f"{chat.id}:"):
                        group_warnings += 1
                        
            except:
                pass
            
            await query.edit_message_text(
                f"📊 *Group Statistics*\n\n"
                f"• Group: {chat.title}\n"
                f"• Members: {member_count}\n"
                f"• Type: {chat.type}\n"
                f"• Warnings: {group_warnings}\n"
                f"• ID: `{chat.id}`\n\n"
                f"_Updated in real-time_",
                reply_markup=Keyboards.group_tools_menu(),
                parse_mode='Markdown'
            )
        
        elif data == "group_bans":
            # This would need actual banned list - simplified
            await query.edit_message_text(
                "🚫 *Banned Users*\n\n"
                "To view banned users, use:\n"
                "• /banlist command\n\n"
                "_Coming soon to menu!_",
                reply_markup=Keyboards.group_tools_menu(),
                parse_mode='Markdown'
            )
        
        elif data == "group_warnings":
            chat = update.effective_chat
            
            # Get warnings for this chat
            chat_warnings = []
            for key, data in warnings_data.items():
                if key.startswith(f"{chat.id}:"):
                    user_id = key.split(":")[1]
                    try:
                        user = await context.bot.get_chat_member(chat.id, int(user_id))
                        username = user.user.username or user.user.first_name
                        chat_warnings.append({
                            "user": username,
                            "warnings": data.get("warnings", 0)
                        })
                    except:
                        continue
            
            if not chat_warnings:
                msg = "✅ No warnings in this group!"
            else:
                msg = "⚠️ *Top Warnings*\n\n"
                for w in sorted(chat_warnings, key=lambda x: x["warnings"], reverse=True)[:5]:
                    msg += f"• {w['user']}: {w['warnings']} warnings\n"
            
            await query.edit_message_text(msg, reply_markup=Keyboards.group_tools_menu(), parse_mode='Markdown')
        
        # Admin menu buttons
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
            total_warnings = len(warnings_data)
            
            stats_text = f"""
📊 *Admin Statistics*

━━━━━━━━━━━━━━━━━━━━━
👥 Total Users: {user_count}
📱 Active Today: {active_today}
💬 Groups: {group_count}
🔄 Messages: {total_messages}
⚠️ Warnings: {total_warnings}
━━━━━━━━━━━━━━━━━━━━━

*Groups List:*
{', '.join([g.get('title', 'Unknown') for g in group_data.values()][:5]) or 'None'}
"""
            await query.edit_message_text(stats_text, reply_markup=Keyboards.admin_panel(), parse_mode='Markdown')
        
        elif data == "admin_broadcast":
            if update.effective_user.id != ADMIN_ID:
                await query.edit_message_text("❌ Admin access required!")
                return
            
            success_count = 0
            fail_count = 0
            
            for user_id in user_data.keys():
                try:
                    await context.bot.send_message(
                        chat_id=int(user_id),
                        text="📢 *Broadcast Message*\n\nHello from Alita Assistant! This is a system broadcast.\n\nStay tuned for updates! 🌟",
                        parse_mode='Markdown'
                    )
                    success_count += 1
                    await asyncio.sleep(0.1)
                except:
                    fail_count += 1
            
            await query.edit_message_text(
                f"📢 *Broadcast Results*\n\n✅ Sent: {success_count}\n❌ Failed: {fail_count}",
                reply_markup=Keyboards.admin_panel(),
                parse_mode='Markdown'
            )
        
        elif data == "admin_channel":
            if update.effective_user.id != ADMIN_ID:
                await query.edit_message_text("❌ Admin access required!")
                return
            
            await ChannelMonitor.check_channel_activity(context)
            await query.edit_message_text(
                "✅ Channel check completed!\nCheck your PM for the report.",
                reply_markup=Keyboards.admin_panel()
            )
        
        elif data == "admin_auto":
            if update.effective_user.id != ADMIN_ID:
                await query.edit_message_text("❌ Admin access required!")
                return
            
            await AutoMessaging.send_auto_message(context, update.effective_chat.id)
            await query.edit_message_text(
                "✅ Auto message sent to this chat!",
                reply_markup=Keyboards.admin_panel()
            )
        
        elif data == "admin_groups":
            if update.effective_user.id != ADMIN_ID:
                await query.edit_message_text("❌ Admin access required!")
                return
            
            groups_list = "📋 *Groups List*\n\n"
            if group_data:
                for gid, ginfo in list(group_data.items())[:10]:
                    title = ginfo.get('title', 'Unknown')
                    added = ginfo.get('added_date', 'Unknown')[:10]
                    groups_list += f"• {title}\n  ID: `{gid}`\n  Added: {added}\n\n"
            else:
                groups_list += "No groups yet."
            
            await query.edit_message_text(groups_list, reply_markup=Keyboards.admin_panel(), parse_mode='Markdown')
        
        elif data == "admin_moderation":
            if update.effective_user.id != ADMIN_ID:
                await query.edit_message_text("❌ Admin access required!")
                return
            
            mod_text = f"""
🛡️ *Moderation Settings*

━━━━━━━━━━━━━━━━━━━━━
*Current Configuration:*
• Bad words filter: ✅ Active
• Spam protection: ✅ Active
• Flood control: ✅ Active
• Link moderation: ✅ Active
• Caps lock control: ✅ Active

*Warning System:*
• Warning limit: {ModerationSystem.WARN_LIMIT}
• Mute duration (1st): 1 hour
• Mute duration (2nd): 24 hours
• Final action: Ban

*Bad words list:* {len(ModerationSystem.BAD_WORDS)} words
━━━━━━━━━━━━━━━━━━━━━

To modify settings, contact developer.
"""
            await query.edit_message_text(mod_text, reply_markup=Keyboards.admin_panel(), parse_mode='Markdown')
        
        elif data == "admin_bans":
            if update.effective_user.id != ADMIN_ID:
                await query.edit_message_text("❌ Admin access required!")
                return
            
            await query.edit_message_text(
                "🚫 *Ban Management*\n\n"
                "Commands:\n"
                "• /ban @user - Ban user\n"
                "• /unban @user - Unban user\n"
                "• /banlist - List banned users\n\n"
                "_Use these commands in the group._",
                reply_markup=Keyboards.admin_panel(),
                parse_mode='Markdown'
            )
        
        elif data == "admin_warnings":
            if update.effective_user.id != ADMIN_ID:
                await query.edit_message_text("❌ Admin access required!")
                return
            
            total_warnings = len(warnings_data)
            top_offenders = []
            
            for key, data in warnings_data.items():
                user_id = key.split(":")[1] if ":" in key else "unknown"
                top_offenders.append({
                    "user": user_id[:8] + "...",
                    "warnings": data.get("warnings", 0)
                })
            
            top_offenders = sorted(top_offenders, key=lambda x: x["warnings"], reverse=True)[:5]
            
            msg = f"⚠️ *Global Warnings*\n\nTotal: {total_warnings}\n\n*Top Offenders:*\n"
            for o in top_offenders:
                msg += f"• {o['user']}: {o['warnings']} warnings\n"
            
            await query.edit_message_text(msg, reply_markup=Keyboards.admin_panel(), parse_mode='Markdown')
        
        # Back button
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
        logger.error(f"Button error: {e}")
        await query.edit_message_text(
            "❌ Service temporarily unavailable",
            reply_markup=Keyboards.back_only()
        )

# ==================== GROUP HANDLERS ====================
async def group_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle new members joining with enhanced welcome"""
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
                "member_count": 0
            }
            DataManager.save_data(GROUP_FILE, group_data)
            
            # Save to backup
            groups_backup = DataManager.load_data("groups_backup.json", [])
            if group_id not in groups_backup:
                groups_backup.append(group_id)
                DataManager.save_data("groups_backup.json", groups_backup)
            
            welcome_msg = f"""
🤖 *Thanks for adding me to {update.effective_chat.title}!*

━━━━━━━━━━━━━━━━━━━━━
✅ *What I can do:*
• Auto quotes every 10 minutes
• Auto messages every 3 hours
• Welcome new members
• Advanced moderation
• Ban repeat offenders
• Entertainment commands
━━━━━━━━━━━━━━━━━━━━━

📝 *Quick Commands:*
/rules - View group rules
/auto - Trigger manual update
/setinterval - Change frequency
/mywarns - Check your warnings

Use /help for full command list!

_Let's make this group awesome together!_ 🚀
"""
            await update.message.reply_text(welcome_msg, parse_mode='Markdown')
            
        else:
            # Welcome new user with enhanced templates
            welcome_templates = [
                f"""
━━━━━━━━━━━━━━━━━━━━━
🌟 *Welcome to the Family!* 🌟
━━━━━━━━━━━━━━━━━━━━━

👋 Hey {member.first_name}! We're thrilled to have you here!

✨ *Quick Tips:*
• Introduce yourself to everyone
• Check out /rules to know the guidelines
• Use /help to see what I can do
• Be respectful and have fun!

━━━━━━━━━━━━━━━━━━━━━
Welcome aboard! 🎉
""",
                f"""
━━━━━━━━━━━━━━━━━━━━━
🎊 *New Member Alert!* 🎊
━━━━━━━━━━━━━━━━━━━━━

Please give a warm welcome to **{member.first_name}**! 👋

💫 *About the group:*
We're a friendly community here. Feel free to jump into conversations, ask questions, and share your thoughts!

📌 Don't forget to read /rules

━━━━━━━━━━━━━━━━━━━━━
Glad to have you here! 🌟
""",
                f"""
━━━━━━━━━━━━━━━━━━━━━
✨ *Welcome Aboard!* ✨
━━━━━━━━━━━━━━━━━━━━━

Hey {member.first_name}! Thanks for joining us! 

🚀 *What you can do:*
• Chat with awesome people
• Get daily quotes every 10min
• Ask for jokes, facts, music
• Stay updated with auto messages

━━━━━━━━━━━━━━━━━━━━━
Enjoy your stay! 🎈
"""
            ]
            
            welcome_msg = random.choice(welcome_templates)
            await update.message.reply_text(welcome_msg, parse_mode='Markdown')
            
            # Send private welcome message
            try:
                private_welcome = f"""
👋 Hello {member.first_name}!

Thanks for joining **{update.effective_chat.title}**! I'm Alita Assistant, your friendly neighborhood bot.

✨ *I can help you with:*
• Daily inspirational quotes (every 10 min!)
• Jokes, facts, and music suggestions
• Weather updates
• Group rules and information

Use /help in the group to see all commands.

Hope you have a wonderful time! 🌟
"""
                await context.bot.send_message(
                    chat_id=member.id,
                    text=private_welcome,
                    parse_mode='Markdown'
                )
            except:
                pass  # User might have privacy settings

async def group_left(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle members leaving"""
    left_member = update.message.left_chat_member
    if left_member and left_member.id != context.bot.id:
        # Send goodbye message 30% of the time
        if random.random() < 0.3:
            goodbyes = [
                f"👋 Goodbye {left_member.first_name}! Sorry to see you go!",
                f"😢 Sad to see you leave {left_member.first_name}! Take care!",
                f"👋 Until we meet again {left_member.first_name}! All the best!",
                f"🌟 {left_member.first_name} has left the group. We'll miss you!"
            ]
            goodbye = random.choice(goodbyes)
            await update.message.reply_text(goodbye)

# ==================== ERROR HANDLER ====================
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log errors"""
    logger.error(f"Exception: {context.error}")

# ==================== PERIODIC TASK STARTER ====================
async def start_periodic_messages(application: Application):
    """Start all periodic tasks"""
    async def periodic_wrapper():
        await asyncio.sleep(30)  # Wait 30 seconds after startup
        while True:
            try:
                class SimpleContext:
                    def __init__(self, bot):
                        self.bot = bot
                
                context = SimpleContext(application.bot)
                
                # Run regular auto messages
                await periodic_group_messages(context)
                
                # Run quotes every cycle
                await periodic_quotes(context)
                
                # Random channel checks
                if random.random() < 0.1:  # 10% chance each cycle
                    await ChannelMonitor.check_channel_activity(context)
                
                # Wait 5 minutes before next check
                # (quotes are controlled by scheduler, this is just the check loop)
                await asyncio.sleep(300)  # Check every 5 minutes
                
            except Exception as e:
                logger.error(f"Periodic error: {e}")
                await asyncio.sleep(60)
    
    # Create and start the task
    asyncio.create_task(periodic_wrapper())
    logger.info("✅ All periodic tasks started (quotes every 10min, messages every 3h)")

# ==================== HEALTH CHECK ====================
async def health_check(request):
    """Simple health check endpoint"""
    return aiohttp.web.Response(
        text="OK",
        status=200,
        headers={'Content-Type': 'text/plain'}
    )

async def run_web_server():
    """Run a simple web server for health checks"""
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
        
        logger.info(f"✅ Health check server running on port {port}")
        return runner
    except Exception as e:
        logger.error(f"⚠️ Health check server not started: {e}")
        return None

# ==================== MAIN ====================
def main():
    """Main function to run the bot"""
    def signal_handler(signum, frame):
        logger.info("🔄 Shutting down gracefully...")
        # Save all data
        DataManager.save_data(USER_FILE, user_data)
        DataManager.save_data(GROUP_FILE, group_data)
        DataManager.save_data(SETTINGS_FILE, bot_settings)
        DataManager.save_data(CHANNEL_FILE, channel_data)
        DataManager.save_data(SCHEDULE_FILE, {
            "messages": {k: v.isoformat() for k, v in scheduler.last_message_time.items()},
            "quotes": {k: v.isoformat() for k, v in scheduler.last_quote_time.items()}
        })
        DataManager.save_data(WARNINGS_FILE, warnings_data)
        logger.info("✅ All data saved. Goodbye!")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
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
    application.add_handler(CommandHandler("mywarns", my_warnings_command))
    application.add_handler(CommandHandler("warnings", warnings_command))
    application.add_handler(CommandHandler("ban", ban_command))
    application.add_handler(CommandHandler("unban", unban_command))
    application.add_handler(CommandHandler("mute", mute_command))
    
    # Button handlers
    application.add_handler(CallbackQueryHandler(button_handler))
    
    # Message handlers - ONLY ONE handler for text messages
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_main_menu))
    
    # Group handlers
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, group_welcome))
    application.add_handler(MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER, group_left))
    
    # Set bot commands and start background tasks
    async def post_init(application: Application):
        # Set bot commands
        await application.bot.set_my_commands([
            BotCommand("start", "Start bot"),
            BotCommand("help", "Help guide"),
            BotCommand("status", "Bot status"),
            BotCommand("rules", "Group rules"),
            BotCommand("auto", "Trigger auto msg"),
            BotCommand("mywarns", "Check your warnings"),
            BotCommand("setinterval", "Set interval"),
            BotCommand("toggleauto", "Toggle auto")
        ])
        logger.info("✅ Bot commands configured")
        
        # Start periodic tasks
        await start_periodic_messages(application)
        
        # Start health check server
        asyncio.create_task(run_web_server())
        
        logger.info("✅ Bot initialization complete!")
    
    application.post_init = post_init
    
    # Startup message
    logger.info("🚀 Starting Alita Assistant...")
    logger.info(f"👑 Admin ID: {ADMIN_ID}")
    logger.info(f"👥 Loaded users: {len(user_data)}")
    logger.info(f"💬 Loaded groups: {len(group_data)}")
    logger.info(f"⚠️ Loaded warnings: {len(warnings_data)}")
    
    try:
        # Run the bot
        application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True
        )
    except Exception as e:
        logger.error(f"❌ Bot failed: {e}")
        # Save data before exiting
        DataManager.save_data(USER_FILE, user_data)
        DataManager.save_data(GROUP_FILE, group_data)
        DataManager.save_data(SETTINGS_FILE, bot_settings)
        DataManager.save_data(CHANNEL_FILE, channel_data)
        DataManager.save_data(WARNINGS_FILE, warnings_data)
        sys.exit(1)

if __name__ == "__main__":
    main()
