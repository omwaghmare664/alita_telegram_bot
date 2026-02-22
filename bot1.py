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
from telegram.constants import ParseMode
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
from collections import defaultdict, deque
import time

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
WARNINGS_FILE = "warnings.json"
MUTES_FILE = "mutes.json"
BANS_FILE = "bans.json"
FILTERS_FILE = "filters.json"

# Create empty files if they don't exist
for file in [USER_FILE, GROUP_FILE, SETTINGS_FILE, WARNINGS_FILE, MUTES_FILE, BANS_FILE, FILTERS_FILE]:
    if not os.path.exists(file):
        DataManager.save_data(file, {})

user_data = DataManager.load_data(USER_FILE, {})
group_data = DataManager.load_data(GROUP_FILE, {})
warnings_data = DataManager.load_data(WARNINGS_FILE, {})
mutes_data = DataManager.load_data(MUTES_FILE, {})
bans_data = DataManager.load_data(BANS_FILE, {})
filters_data = DataManager.load_data(FILTERS_FILE, {})
bot_settings = DataManager.load_data(SETTINGS_FILE, {
    "welcome_message": True,
    "goodbye_message": True,
    "anti_spam": True,
    "anti_flood": True,
    "anti_link": True,
    "warn_limit": 3
})

# ==================== SPAM PROTECTION SYSTEM ====================
class SpamProtection:
    def __init__(self):
        self.message_history = defaultdict(lambda: deque(maxlen=10))  # Store last 10 messages per user
        self.spam_count = defaultdict(int)  # Count spam offenses
        self.last_warning_time = defaultdict(float)  # Track when last warning was given
        self.warning_cooldown = 30  # 30 seconds cooldown between warnings
        self.spam_threshold = 5  # 5 messages in a row triggers spam detection
        self.flood_threshold = 10  # 10 messages in 30 seconds triggers flood detection
        
    def check_message(self, user_id: int, chat_id: int, text: str) -> dict:
        """Check if message is spam and return result"""
        now = time.time()
        key = f"{chat_id}:{user_id}"
        
        # Store message with timestamp
        self.message_history[key].append({
            'text': text,
            'time': now
        })
        
        # Check cooldown to prevent spam warnings
        if now - self.last_warning_time[key] < self.warning_cooldown:
            return {'is_spam': False, 'reason': None}
        
        # Check for duplicate messages (copy-paste spam)
        recent_texts = [msg['text'] for msg in self.message_history[key] if now - msg['time'] < 30]
        if len(recent_texts) >= self.spam_threshold and len(set(recent_texts)) <= 2:
            self.spam_count[key] += 1
            self.last_warning_time[key] = now
            return {
                'is_spam': True, 
                'reason': 'spam',
                'details': f'Repeated {len(recent_texts)} similar messages'
            }
        
        # Check for message flooding (too many messages)
        recent_messages = [msg for msg in self.message_history[key] if now - msg['time'] < 30]
        if len(recent_messages) >= self.flood_threshold:
            self.spam_count[key] += 1
            self.last_warning_time[key] = now
            return {
                'is_spam': True, 
                'reason': 'flood',
                'details': f'{len(recent_messages)} messages in 30 seconds'
            }
        
        # Reset spam count if behaving
        if len(recent_messages) < 3:
            self.spam_count[key] = max(0, self.spam_count[key] - 1)
        
        return {'is_spam': False, 'reason': None}
    
    def get_spam_count(self, user_id: int, chat_id: int) -> int:
        """Get spam count for user"""
        key = f"{chat_id}:{user_id}"
        return self.spam_count[key]

# Initialize spam protection
spam_protection = SpamProtection()

# ==================== MODERATION SYSTEM (LIKE ROSE) ====================
class ModerationSystem:
    def __init__(self):
        self.bad_words = [
            'fuck', 'shit', 'asshole', 'bastard', 'bitch', 'damn', 'hell',
            'fck', 'f*ck', 'bch', 'bsdk', 'mc', 'bc', 'motherfucker',
            'dick', 'pussy', 'cunt', 'whore', 'slut', 'nigger', 'faggot',
            'chutiya', 'madarchod', 'bhenchod', 'lund', 'gandu', 'randi'
        ]
        
    def check_message(self, text: str) -> dict:
        """Check message for violations"""
        text_lower = text.lower()
        violations = []
        
        # Check for bad words
        for word in self.bad_words:
            if word in text_lower:
                violations.append({
                    'type': 'bad_word',
                    'word': word,
                    'severity': 2
                })
                break
        
        # Check for excessive caps (50%+ caps)
        if len(text) > 10:
            caps_count = sum(1 for c in text if c.isupper())
            if caps_count / len(text) > 0.5:
                violations.append({
                    'type': 'excessive_caps',
                    'severity': 1
                })
        
        # Check for links (without whitelist)
        if 'http://' in text_lower or 'https://' in text_lower or 'www.' in text_lower:
            violations.append({
                'type': 'link',
                'severity': 2
            })
        
        # Check for invites
        if 't.me/' in text_lower or 'telegram.me/' in text_lower:
            violations.append({
                'type': 'invite',
                'severity': 3
            })
        
        return violations[0] if violations else None

# Initialize moderation
mod_system = ModerationSystem()

# ==================== WARNING SYSTEM ====================
class WarningSystem:
    def __init__(self):
        self.warning_limit = 3  # Warnings before mute
        self.mute_durations = {
            1: 3600,      # 1 hour
            2: 86400,     # 24 hours
            3: 604800     # 1 week
        }
    
    def add_warning(self, user_id: int, chat_id: int, reason: str, admin_id: int = None) -> dict:
        """Add a warning to user"""
        key = f"{chat_id}:{user_id}"
        
        if key not in warnings_data:
            warnings_data[key] = {
                'user_id': user_id,
                'chat_id': chat_id,
                'warnings': [],
                'total': 0,
                'muted_until': None,
                'banned': False
            }
        
        warning = {
            'reason': reason,
            'date': datetime.now().isoformat(),
            'admin': admin_id or 'system'
        }
        
        warnings_data[key]['warnings'].append(warning)
        warnings_data[key]['total'] = len(warnings_data[key]['warnings'])
        
        DataManager.save_data(WARNINGS_FILE, warnings_data)
        
        return {
            'total': warnings_data[key]['total'],
            'limit': self.warning_limit,
            'warning': warning
        }
    
    def get_warnings(self, user_id: int, chat_id: int) -> dict:
        """Get warnings for user"""
        key = f"{chat_id}:{user_id}"
        data = warnings_data.get(key, {'total': 0, 'warnings': []})
        return {
            'total': data['total'],
            'warnings': data['warnings'][-5:],  # Last 5 warnings
            'limit': self.warning_limit
        }
    
    def clear_warnings(self, user_id: int, chat_id: int) -> bool:
        """Clear all warnings for user"""
        key = f"{chat_id}:{user_id}"
        if key in warnings_data:
            del warnings_data[key]
            DataManager.save_data(WARNINGS_FILE, warnings_data)
            return True
        return False
    
    def should_take_action(self, user_id: int, chat_id: int) -> Optional[dict]:
        """Check if action should be taken based on warnings"""
        key = f"{chat_id}:{user_id}"
        data = warnings_data.get(key, {'total': 0})
        
        total = data['total']
        
        if total >= self.warning_limit + 2:  # 5+ warnings = ban
            return {'action': 'ban', 'level': 'permanent'}
        elif total >= self.warning_limit + 1:  # 4 warnings = mute 1 week
            return {'action': 'mute', 'duration': self.mute_durations[3]}
        elif total >= self.warning_limit:  # 3 warnings = mute 24 hours
            return {'action': 'mute', 'duration': self.mute_durations[2]}
        elif total >= self.warning_limit - 1:  # 2 warnings = mute 1 hour
            return {'action': 'mute', 'duration': self.mute_durations[1]}
        
        return None

# Initialize warning system
warning_system = WarningSystem()

# ==================== FREE API SERVICES ====================
class FreeAPIServices:
    @staticmethod
    async def get_weather(city: str = "London") -> str:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"http://wttr.in/{city}?format=%C+%t+%h+%w", timeout=10) as response:
                    if response.status == 200:
                        data = await response.text()
                        return f"🌤 *Weather in {city.title()}*\n`{data.strip()}`"
        except Exception as e:
            logger.error(f"Weather API error: {e}")
            return f"🌤 *Weather in {city.title()}*\n`☀️ 25°C • 💧 60% • 🌬 10km/h`"

    @staticmethod
    async def get_joke() -> str:
        jokes = [
            "Why don't scientists trust atoms? Because they make up everything!",
            "What do you call a fake noodle? An impasta!",
            "Why did the scarecrow win an award? He was outstanding in his field!",
            "Why don't eggs tell jokes? They'd crack each other up!",
            "What do you call a sleeping bull? A bulldozer!",
            "Why did the math book look sad? Because it had too many problems!"
        ]
        return f"😂 *Joke*\n{random.choice(jokes)}"

    @staticmethod
    async def get_quote() -> str:
        quotes = [
            ("The only way to do great work is to love what you do.", "Steve Jobs"),
            ("Success is not final, failure is not fatal.", "Winston Churchill"),
            ("Believe you can and you're halfway there.", "Theodore Roosevelt"),
            ("The future belongs to those who believe in the beauty of their dreams.", "Eleanor Roosevelt"),
            ("Life is what happens when you're busy making other plans.", "John Lennon")
        ]
        quote, author = random.choice(quotes)
        return f"💭 *Quote*\n“{quote}”\n— {author}"

    @staticmethod
    async def get_fact() -> str:
        facts = [
            "Honey never spoils. Archaeologists found 3000-year-old honey that's still good!",
            "Octopuses have three hearts and blue blood.",
            "A day on Venus is longer than a year on Venus.",
            "Bananas are berries, but strawberries aren't.",
            "The shortest war in history lasted only 38 minutes."
        ]
        return f"📚 *Fact*\n{random.choice(facts)}"

    @staticmethod
    async def get_song() -> str:
        songs = [
            ("Kesariya", "Brahmāstra"),
            ("Apna Bana Le", "Bhediya"),
            ("Flowers", "Miley Cyrus"),
            ("Anti-Hero", "Taylor Swift"),
            ("Pasoori", "Coke Studio")
        ]
        song, artist = random.choice(songs)
        return f"🎵 *Song Suggestion*\n**{song}** by {artist}"

# ==================== AUTO MESSAGES ====================
class AutoMessages:
    @staticmethod
    async def get_daily_message():
        messages = [
            f"🌟 *Daily Inspiration*\n{random.choice(['Keep going!', 'You got this!', 'Stay positive!'])}",
            f"💡 *Tip of the Day*\n{random.choice(['Drink water', 'Take breaks', 'Be kind'])}",
            await FreeAPIServices.get_quote(),
            await FreeAPIServices.get_joke(),
            await FreeAPIServices.get_fact()
        ]
        return random.choice(messages)
    
    @staticmethod
    async def send_auto_message(context, chat_id: int):
        try:
            msg = await AutoMessages.get_daily_message()
            await context.bot.send_message(
                chat_id=chat_id,
                text=msg,
                parse_mode=ParseMode.MARKDOWN
            )
            return True
        except Exception as e:
            logger.error(f"Auto message failed: {e}")
            return False

# ==================== KEYBOARDS ====================
class Keyboards:
    @staticmethod
    def main_menu():
        return ReplyKeyboardMarkup([
            [KeyboardButton("🌤 Weather"), KeyboardButton("😂 Joke")],
            [KeyboardButton("💭 Quote"), KeyboardButton("📚 Fact")],
            [KeyboardButton("🎵 Song"), KeyboardButton("🛠 Tools")],
            [KeyboardButton("👥 Group"), KeyboardButton("👑 Admin")]
        ], resize_keyboard=True)
    
    @staticmethod
    def group_menu():
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("👋 Welcome", callback_data="group_welcome"),
             InlineKeyboardButton("🛡 Rules", callback_data="group_rules")],
            [InlineKeyboardButton("⚠️ Warnings", callback_data="group_warnings"),
             InlineKeyboardButton("🚫 Bans", callback_data="group_bans")],
            [InlineKeyboardButton("🔙 Back", callback_data="back_main")]
        ])
    
    @staticmethod
    def admin_menu():
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("📊 Stats", callback_data="admin_stats"),
             InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")],
            [InlineKeyboardButton("🛡 Moderation", callback_data="admin_mod"),
             InlineKeyboardButton("📋 Groups", callback_data="admin_groups")],
            [InlineKeyboardButton("🔙 Back", callback_data="back_main")]
        ])
    
    @staticmethod
    def back_only():
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data="back_main")]
        ])

# ==================== COMMAND HANDLERS ====================
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    welcome = f"""
👋 *Welcome {user.first_name}!*

I'm a powerful group management bot like Rose. I can help you with:

• 🛡 *Moderation* - Warn, mute, ban
• 🤖 *Anti-Spam* - Block flood & spam
• 👋 *Greetings* - Welcome/Goodbye messages
• 📊 *Statistics* - Track group activity
• 🎮 *Fun* - Jokes, quotes, facts

Use the buttons below to get started!
"""
    await update.message.reply_text(
        welcome,
        reply_markup=Keyboards.main_menu(),
        parse_mode=ParseMode.MARKDOWN
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
📚 *Commands*

*User Commands:*
/start - Start the bot
/help - Show this help
/rules - Group rules
/report - Report a user
/mywarns - Check your warns

*Admin Commands:*
/warn @user - Warn user
/unwarn @user - Remove warn
/mute @user - Mute user
/unmute @user - Unmute user
/ban @user - Ban user
/unban @user - Unban user
/purge - Delete messages
/slowmode - Set slowmode

*Settings:*
/setwelcome - Set welcome msg
/setgoodbye - Set goodbye msg
/addfilter - Add word filter
/removefilter - Remove filter
"""
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)

async def rules_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rules = """
📜 *Group Rules*

1. Be respectful to everyone
2. No spam or flooding
3. No inappropriate language
4. No harassment or bullying
5. No promotional content
6. Follow admin instructions

*Violations will result in warnings, mutes, or bans.*
"""
    await update.message.reply_text(rules, parse_mode=ParseMode.MARKDOWN)

async def mywarns_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    
    warns = warning_system.get_warnings(user.id, chat.id)
    
    if warns['total'] == 0:
        msg = f"✅ {user.first_name}, you have no warnings. Good job!"
    else:
        msg = f"⚠️ *Warnings for {user.first_name}*\nTotal: {warns['total']}/{warns['limit']}\n\n"
        for i, w in enumerate(warns['warnings'][-3:], 1):
            msg += f"{i}. {w['reason']} ({w['date'][:10]})\n"
    
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

async def warn_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Admin only!")
        return
    
    if not context.args:
        await update.message.reply_text("Usage: /warn @user [reason]")
        return
    
    try:
        # Parse user and reason
        target = context.args[0].replace("@", "")
        reason = ' '.join(context.args[1:]) if len(context.args) > 1 else "No reason"
        
        # Find user in chat
        chat = update.effective_chat
        user_to_warn = None
        
        async for member in chat.get_members():
            if member.user.username and member.user.username.lower() == target.lower():
                user_to_warn = member.user
                break
        
        if not user_to_warn:
            await update.message.reply_text("❌ User not found!")
            return
        
        # Add warning
        result = warning_system.add_warning(
            user_to_warn.id, 
            chat.id, 
            reason,
            update.effective_user.id
        )
        
        # Send warning message
        warn_msg = f"""
⚠️ *User Warned*

**User:** {user_to_warn.first_name}
**Reason:** {reason}
**Warnings:** {result['total']}/{result['limit']}
**Admin:** {update.effective_user.first_name}

Please follow group rules.
"""
        await update.message.reply_text(warn_msg, parse_mode=ParseMode.MARKDOWN)
        
        # Check if action needed
        action = warning_system.should_take_action(user_to_warn.id, chat.id)
        if action:
            await take_action(update, context, user_to_warn, action)
            
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def take_action(update: Update, context: ContextTypes.DEFAULT_TYPE, user, action):
    """Take moderation action based on warnings"""
    chat = update.effective_chat
    
    if action['action'] == 'mute':
        # Mute user
        permissions = ChatPermissions(
            can_send_messages=False,
            can_send_media_messages=False,
            can_send_polls=False,
            can_send_other_messages=False
        )
        
        until = datetime.now() + timedelta(seconds=action['duration'])
        await context.bot.restrict_chat_member(
            chat_id=chat.id,
            user_id=user.id,
            permissions=permissions,
            until_date=until
        )
        
        hours = action['duration'] // 3600
        mute_msg = f"""
🔇 *User Muted*

**User:** {user.first_name}
**Duration:** {hours} hours
**Reason:** Reached warning limit

Contact admins to appeal.
"""
        await context.bot.send_message(chat.id, mute_msg, parse_mode=ParseMode.MARKDOWN)
        
    elif action['action'] == 'ban':
        # Ban user
        await context.bot.ban_chat_member(chat.id, user.id)
        
        ban_msg = f"""
🚫 *User Banned*

**User:** {user.first_name}
**Reason:** Excessive warnings
**Action:** Permanent ban

This user has been removed from the group.
"""
        await context.bot.send_message(chat.id, ban_msg, parse_mode=ParseMode.MARKDOWN)

# ==================== MESSAGE HANDLER ====================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Main message handler"""
    if not update.message or not update.message.text:
        return
    
    user = update.effective_user
    chat = update.effective_chat
    text = update.message.text
    
    # Handle private chats
    if chat.type == "private":
        await handle_private_message(update, context)
        return
    
    # Handle group messages
    if chat.type in ["group", "supergroup"]:
        await handle_group_message(update, context)

async def handle_private_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle private chat messages"""
    text = update.message.text
    
    if text == "🌤 Weather":
        weather = await FreeAPIServices.get_weather()
        await update.message.reply_text(weather, parse_mode=ParseMode.MARKDOWN)
    
    elif text == "😂 Joke":
        joke = await FreeAPIServices.get_joke()
        await update.message.reply_text(joke, parse_mode=ParseMode.MARKDOWN)
    
    elif text == "💭 Quote":
        quote = await FreeAPIServices.get_quote()
        await update.message.reply_text(quote, parse_mode=ParseMode.MARKDOWN)
    
    elif text == "📚 Fact":
        fact = await FreeAPIServices.get_fact()
        await update.message.reply_text(fact, parse_mode=ParseMode.MARKDOWN)
    
    elif text == "🎵 Song":
        song = await FreeAPIServices.get_song()
        await update.message.reply_text(song, parse_mode=ParseMode.MARKDOWN)
    
    elif text == "🛠 Tools":
        tools = "🛠 *Tools*\n\n• /weather [city]\n• /joke\n• /quote\n• /fact\n• /song"
        await update.message.reply_text(tools, parse_mode=ParseMode.MARKDOWN)
    
    elif text == "👥 Group":
        await update.message.reply_text(
            "Add me to a group and make me admin to use group features!",
            reply_markup=Keyboards.group_menu(),
            parse_mode=ParseMode.MARKDOWN
        )
    
    elif text == "👑 Admin":
        if user.id != ADMIN_ID:
            await update.message.reply_text("❌ Admin only!")
            return
        await update.message.reply_text(
            "👑 *Admin Panel*",
            reply_markup=Keyboards.admin_menu(),
            parse_mode=ParseMode.MARKDOWN
        )
    
    else:
        # Smart replies
        text_lower = text.lower()
        if any(word in text_lower for word in ['hello', 'hi', 'hey']):
            await update.message.reply_text(f"👋 Hello {user.first_name}!")
        elif any(word in text_lower for word in ['thanks', 'thank you']):
            await update.message.reply_text("😊 You're welcome!")

async def handle_group_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle group messages with moderation"""
    user = update.effective_user
    chat = update.effective_chat
    text = update.message.text
    
    # Check for commands in group
    if text.startswith('/'):
        return
    
    # Update user data
    user_id = str(user.id)
    if user_id not in user_data:
        user_data[user_id] = {
            'first_seen': datetime.now().isoformat(),
            'username': user.username,
            'first_name': user.first_name,
            'messages': 0
        }
    user_data[user_id]['messages'] = user_data[user_id].get('messages', 0) + 1
    DataManager.save_data(USER_FILE, user_data)
    
    # Check for spam
    spam_check = spam_protection.check_message(user.id, chat.id, text)
    if spam_check['is_spam']:
        spam_count = spam_protection.get_spam_count(user.id, chat.id)
        
        # Add warning for spam
        warning_system.add_warning(
            user.id, 
            chat.id, 
            f"Spam: {spam_check['details']}",
            'system'
        )
        
        warns = warning_system.get_warnings(user.id, chat.id)
        
        # Delete spam message
        try:
            await update.message.delete()
        except:
            pass
        
        # Send warning
        warn_msg = f"""
⚠️ *Spam Detected*
User: {user.first_name}
Reason: {spam_check['details']}
Warning: {warns['total']}/{warning_system.warning_limit}

Please don't spam.
"""
        warning = await update.message.reply_text(warn_msg, parse_mode=ParseMode.MARKDOWN)
        
        # Auto-delete warning after 10 seconds
        await asyncio.sleep(10)
        try:
            await warning.delete()
        except:
            pass
        
        # Check if action needed
        action = warning_system.should_take_action(user.id, chat.id)
        if action:
            await take_action(update, context, user, action)
        
        return
    
    # Check for bad words/moderation
    violation = mod_system.check_message(text)
    if violation:
        # Add warning
        warning_system.add_warning(
            user.id,
            chat.id,
            f"{violation['type'].replace('_', ' ').title()}",
            'system'
        )
        
        warns = warning_system.get_warnings(user.id, chat.id)
        
        # Delete violating message
        try:
            await update.message.delete()
        except:
            pass
        
        # Send warning
        warn_msg = f"""
⚠️ *Rule Violation*
User: {user.first_name}
Reason: {violation['type'].replace('_', ' ').title()}
Warning: {warns['total']}/{warning_system.warning_limit}

Please follow group rules.
"""
        warning = await update.message.reply_text(warn_msg, parse_mode=ParseMode.MARKDOWN)
        
        # Auto-delete warning after 10 seconds
        await asyncio.sleep(10)
        try:
            await warning.delete()
        except:
            pass
        
        # Check if action needed
        action = warning_system.should_take_action(user.id, chat.id)
        if action:
            await take_action(update, context, user, action)

# ==================== GROUP HANDLERS ====================
async def group_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle new members"""
    for member in update.message.new_chat_members:
        if member.id == context.bot.id:
            # Bot was added
            group_id = str(update.effective_chat.id)
            group_data[group_id] = {
                'title': update.effective_chat.title,
                'added': datetime.now().isoformat()
            }
            DataManager.save_data(GROUP_FILE, group_data)
            
            await update.message.reply_text(
                f"🤖 *Thanks for adding me!*\n\n"
                f"Make me **admin** to work properly!\n"
                f"Use /help to see commands.",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            # New user joined
            welcome = f"""
👋 *Welcome {member.first_name}!*

Glad to have you here! 
Read /rules and enjoy your stay! 🎉
"""
            await update.message.reply_text(welcome, parse_mode=ParseMode.MARKDOWN)

async def group_left(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle members leaving"""
    member = update.message.left_chat_member
    if member and member.id != context.bot.id:
        goodbye = f"👋 Goodbye {member.first_name}! Sorry to see you go."
        await update.message.reply_text(goodbye)

# ==================== BUTTON HANDLER ====================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data == "group_welcome":
        await query.edit_message_text(
            "👋 *Welcome Settings*\n\n"
            "• Welcome messages: ✅ ON\n"
            "• Goodbye messages: ✅ ON\n\n"
            "Use /setwelcome to customize",
            reply_markup=Keyboards.back_only(),
            parse_mode=ParseMode.MARKDOWN
        )
    
    elif data == "group_rules":
        await query.edit_message_text(
            "🛡 *Rules*\n\n"
            "• Be respectful\n"
            "• No spam\n"
            "• No bad words\n"
            "• Follow admins",
            reply_markup=Keyboards.back_only(),
            parse_mode=ParseMode.MARKDOWN
        )
    
    elif data == "group_warnings":
        # Count total warnings
        total = len(warnings_data)
        await query.edit_message_text(
            f"⚠️ *Warnings*\n\nTotal active: {total}",
            reply_markup=Keyboards.back_only(),
            parse_mode=ParseMode.MARKDOWN
        )
    
    elif data == "group_bans":
        total = len(bans_data)
        await query.edit_message_text(
            f"🚫 *Bans*\n\nTotal banned: {total}",
            reply_markup=Keyboards.back_only(),
            parse_mode=ParseMode.MARKDOWN
        )
    
    elif data == "admin_stats":
        if update.effective_user.id != ADMIN_ID:
            await query.edit_message_text("❌ Admin only!")
            return
        
        stats = f"""
📊 *Bot Statistics*

**Users:** {len(user_data)}
**Groups:** {len(group_data)}
**Warnings:** {len(warnings_data)}
**Bans:** {len(bans_data)}
"""
        await query.edit_message_text(
            stats,
            reply_markup=Keyboards.admin_menu(),
            parse_mode=ParseMode.MARKDOWN
        )
    
    elif data == "admin_broadcast":
        if update.effective_user.id != ADMIN_ID:
            await query.edit_message_text("❌ Admin only!")
            return
        
        await query.edit_message_text(
            "📢 *Broadcast*\n\nUse /broadcast [message]",
            reply_markup=Keyboards.admin_menu(),
            parse_mode=ParseMode.MARKDOWN
        )
    
    elif data == "admin_mod":
        if update.effective_user.id != ADMIN_ID:
            await query.edit_message_text("❌ Admin only!")
            return
        
        mod = f"""
🛡 *Moderation Settings*

**Warn Limit:** {warning_system.warning_limit}
**Spam Threshold:** {spam_protection.spam_threshold}
**Flood Threshold:** {spam_protection.flood_threshold}

**Mute Durations:**
• 1st: 1 hour
• 2nd: 24 hours
• 3rd: 1 week
"""
        await query.edit_message_text(
            mod,
            reply_markup=Keyboards.admin_menu(),
            parse_mode=ParseMode.MARKDOWN
        )
    
    elif data == "admin_groups":
        if update.effective_user.id != ADMIN_ID:
            await query.edit_message_text("❌ Admin only!")
            return
        
        groups = "📋 *Groups*\n\n"
        for gid, info in list(group_data.items())[:10]:
            groups += f"• {info.get('title', 'Unknown')}\n"
        
        await query.edit_message_text(
            groups,
            reply_markup=Keyboards.admin_menu(),
            parse_mode=ParseMode.MARKDOWN
        )
    
    elif data == "back_main":
        await query.edit_message_text(
            "🏠 *Main Menu*",
            reply_markup=Keyboards.main_menu(),
            parse_mode=ParseMode.MARKDOWN
        )

# ==================== PERIODIC TASKS ====================
async def periodic_tasks(app: Application):
    """Run periodic tasks"""
    while True:
        try:
            # Send auto messages to groups
            for group_id in group_data:
                await AutoMessages.send_auto_message(app.bot, int(group_id))
                await asyncio.sleep(5)  # Delay between groups
            
            # Wait 1 hour before next cycle
            await asyncio.sleep(3600)
            
        except Exception as e:
            logger.error(f"Periodic task error: {e}")
            await asyncio.sleep(60)

async def post_init(app: Application):
    """Setup after bot starts"""
    # Set commands
    commands = [
        BotCommand("start", "Start the bot"),
        BotCommand("help", "Show help"),
        BotCommand("rules", "Show rules"),
        BotCommand("mywarns", "Check your warnings"),
        BotCommand("report", "Report a user"),
        BotCommand("warn", "Warn user (admin)"),
        BotCommand("unwarn", "Remove warn (admin)"),
        BotCommand("mute", "Mute user (admin)"),
        BotCommand("ban", "Ban user (admin)"),
        BotCommand("unban", "Unban user (admin)")
    ]
    await app.bot.set_my_commands(commands)
    logger.info("✅ Commands set")
    
    # Start periodic tasks
    asyncio.create_task(periodic_tasks(app))
    logger.info("✅ Periodic tasks started")

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

# ==================== ERROR HANDLER ====================
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} caused error {context.error}")

# ==================== MAIN ====================
def main():
    def signal_handler(signum, frame):
        logger.info("Shutting down...")
        DataManager.save_data(USER_FILE, user_data)
        DataManager.save_data(GROUP_FILE, group_data)
        DataManager.save_data(WARNINGS_FILE, warnings_data)
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Create app
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("rules", rules_command))
    app.add_handler(CommandHandler("mywarns", mywarns_command))
    app.add_handler(CommandHandler("warn", warn_command))
    
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, group_welcome))
    app.add_handler(MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER, group_left))
    
    app.add_error_handler(error_handler)
    app.post_init = post_init
    
    # Start web server
    asyncio.create_task(run_web_server())
    
    # Start bot
    logger.info("🚀 Starting bot...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
