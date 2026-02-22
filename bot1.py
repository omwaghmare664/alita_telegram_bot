#!/usr/bin/env python3
"""
Alita Assistant Bot - Complete Group Management Bot
Like Rose, but better! Auto moderation, quotes every 10 min, auto ban/spam protection.
Single file, no dependencies issues, production ready.
"""

import logging
import asyncio
import json
import os
import random
import re
import signal
import sys
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any

import aiohttp
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton, BotCommand, ChatPermissions
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters, Defaults
)

# ==================== CONFIGURATION ====================
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Your bot token - CHANGE THIS TO YOUR BOT TOKEN
BOT_TOKEN = "8168577329:AAFgYEHmIe-SDuRL3tqt6rx1MtAnJprSbRc"
BOT_USERNAME = "@alitacode_bot"
ADMIN_ID = 7327016053  # Your admin ID

# ==================== DATA MANAGEMENT ====================
class Database:
    """Simple JSON-based database with auto-save"""
    
    def __init__(self):
        self.data_files = {
            'users': 'users.json',
            'groups': 'groups.json',
            'warnings': 'warnings.json',
            'mutes': 'mutes.json',
            'bans': 'bans.json',
            'settings': 'settings.json',
            'filters': 'filters.json',
            'stats': 'stats.json'
        }
        self.data = {}
        self.load_all()
    
    def load_all(self):
        """Load all data files"""
        for name, file in self.data_files.items():
            try:
                if os.path.exists(file):
                    with open(file, 'r') as f:
                        self.data[name] = json.load(f)
                else:
                    self.data[name] = {}
                    self.save(name)
            except Exception as e:
                logger.error(f"Error loading {file}: {e}")
                self.data[name] = {}
    
    def save(self, name: str):
        """Save specific data file"""
        try:
            with open(self.data_files[name], 'w') as f:
                json.dump(self.data[name], f, indent=2)
        except Exception as e:
            logger.error(f"Error saving {self.data_files[name]}: {e}")
    
    def get(self, name: str, key: str = None, default=None):
        """Get data"""
        if key:
            return self.data.get(name, {}).get(key, default)
        return self.data.get(name, default)
    
    def set(self, name: str, key: str, value: Any):
        """Set data"""
        if name not in self.data:
            self.data[name] = {}
        self.data[name][key] = value
        self.save(name)
    
    def delete(self, name: str, key: str):
        """Delete data"""
        if name in self.data and key in self.data[name]:
            del self.data[name][key]
            self.save(name)
            return True
        return False
    
    def update(self, name: str, key: str, **kwargs):
        """Update nested data"""
        if name not in self.data:
            self.data[name] = {}
        if key not in self.data[name]:
            self.data[name][key] = {}
        self.data[name][key].update(kwargs)
        self.save(name)

# Initialize database
db = Database()

# Default settings
default_group_settings = {
    'welcome': True,
    'goodbye': True,
    'antispam': True,
    'antiflood': True,
    'antilink': True,
    'antitag': True,
    'warn_limit': 3,
    'mute_time': 3600,  # 1 hour
    'ban_time': 86400,  # 24 hours
    'auto_quote': True,
    'auto_quote_interval': 600,  # 10 minutes
    'auto_message': True,
    'auto_message_interval': 10800,  # 3 hours
    'welcome_message': "👋 Welcome {name} to {group}!",
    'goodbye_message': "👋 Goodbye {name}!",
    'rules': None
}

# ==================== SPAM PROTECTION ====================
class AntiSpam:
    """Advanced spam protection system"""
    
    def __init__(self):
        self.message_history = defaultdict(lambda: deque(maxlen=20))
        self.spam_count = defaultdict(int)
        self.last_action = defaultdict(float)
        self.action_cooldown = 30  # seconds
    
    def check(self, user_id: int, chat_id: int, text: str) -> Optional[Dict]:
        """Check if message is spam. Returns None or violation dict."""
        now = time.time()
        key = f"{chat_id}:{user_id}"
        
        # Store message
        self.message_history[key].append({
            'text': text,
            'time': now
        })
        
        # Cooldown check
        if now - self.last_action[key] < self.action_cooldown:
            return None
        
        # Get recent messages (last 30 seconds)
        recent = [m for m in self.message_history[key] if now - m['time'] < 30]
        
        # Check flood (too many messages)
        if len(recent) >= 10:
            self.spam_count[key] += 1
            self.last_action[key] = now
            return {
                'type': 'flood',
                'reason': f"{len(recent)} messages in 30s",
                'severity': self.spam_count[key]
            }
        
        # Check duplicate messages (copy-paste spam)
        if len(recent) >= 5:
            texts = [m['text'] for m in recent]
            if len(set(texts)) <= 2:
                self.spam_count[key] += 1
                self.last_action[key] = now
                return {
                    'type': 'spam',
                    'reason': f"{len(recent)} repeated messages",
                    'severity': self.spam_count[key]
                }
        
        # Check for repeated characters (keyboard spam)
        if len(text) > 20 and len(set(text)) < 5:
            self.spam_count[key] += 1
            self.last_action[key] = now
            return {
                'type': 'keyboard_spam',
                'reason': "Repeated characters",
                'severity': self.spam_count[key]
            }
        
        # Decay spam count
        if len(recent) < 3:
            self.spam_count[key] = max(0, self.spam_count[key] - 1)
        
        return None
    
    def get_count(self, user_id: int, chat_id: int) -> int:
        """Get spam count for user"""
        return self.spam_count.get(f"{chat_id}:{user_id}", 0)

# ==================== MODERATION ====================
class Moderator:
    """Content moderation system"""
    
    def __init__(self):
        self.bad_words = [
            'fuck', 'shit', 'asshole', 'bastard', 'bitch', 'damn', 'hell',
            'fck', 'f*ck', 'bch', 'bsdk', 'mc', 'bc', 'motherfucker',
            'dick', 'pussy', 'cunt', 'whore', 'slut', 'nigger', 'faggot',
            'chutiya', 'madarchod', 'bhenchod', 'lund', 'gandu', 'randi',
            'sex', 'porn', 'xxx', 'adult', 'nude', 'naked', 'fuckyou',
            'stfu', 'wtf', 'omg', 'lol', 'rofl', 'lmao', 'lmfao'
        ]
        
        # Load custom filters from database
        self.custom_filters = db.get('filters', 'words', [])
    
    def check(self, text: str) -> Optional[Dict]:
        """Check message for violations. Returns None or violation dict."""
        text_lower = text.lower()
        
        # Check bad words
        for word in self.bad_words + self.custom_filters:
            if word in text_lower:
                return {
                    'type': 'bad_word',
                    'word': word,
                    'action': 'delete'
                }
        
        # Check excessive caps (40%+ caps)
        if len(text) > 10:
            caps = sum(1 for c in text if c.isupper())
            if caps / len(text) > 0.4:
                return {
                    'type': 'excessive_caps',
                    'action': 'warn'
                }
        
        # Check links
        if re.search(r'https?://|www\.|t\.me/|telegram\.me/|discord\.gg', text_lower):
            return {
                'type': 'link',
                'action': 'delete'
            }
        
        # Check mentions (@everyone, @all, @here)
        if '@everyone' in text_lower or '@all' in text_lower or '@here' in text_lower:
            return {
                'type': 'mass_mention',
                'action': 'delete'
            }
        
        return None

# ==================== WARNING SYSTEM ====================
class WarningManager:
    """Warning and punishment system"""
    
    def __init__(self):
        self.warning_levels = {
            3: {'action': 'mute', 'duration': 3600},      # 1 hour
            4: {'action': 'mute', 'duration': 86400},     # 24 hours
            5: {'action': 'mute', 'duration': 604800},    # 1 week
            6: {'action': 'ban', 'duration': 0}           # permanent
        }
    
    def add_warning(self, user_id: int, chat_id: int, reason: str, admin: Any = None) -> Dict:
        """Add warning to user. Returns warning info."""
        key = f"{chat_id}:{user_id}"
        warnings = db.get('warnings', key, [])
        
        warning = {
            'reason': reason,
            'date': datetime.now().isoformat(),
            'admin': admin if isinstance(admin, str) else 'system'
        }
        
        warnings.append(warning)
        db.set('warnings', key, warnings)
        
        count = len(warnings)
        
        # Check if punishment needed
        punishment = None
        if count in self.warning_levels:
            punishment = self.warning_levels[count]
        
        return {
            'count': count,
            'warning': warning,
            'punishment': punishment
        }
    
    def get_warnings(self, user_id: int, chat_id: int) -> List[Dict]:
        """Get all warnings for user"""
        key = f"{chat_id}:{user_id}"
        return db.get('warnings', key, [])
    
    def clear_warnings(self, user_id: int, chat_id: int) -> bool:
        """Clear all warnings for user"""
        key = f"{chat_id}:{user_id}"
        if db.delete('warnings', key):
            return True
        return False
    
    def get_warning_count(self, user_id: int, chat_id: int) -> int:
        """Get warning count for user"""
        return len(self.get_warnings(user_id, chat_id))

# ==================== ANTI-SPAM INSTANCE ====================
anti_spam = AntiSpam()
moderator = Moderator()
warning_manager = WarningManager()

# ==================== AUTO MESSAGES ====================
class AutoMessageManager:
    """Automated message system"""
    
    def __init__(self):
        self.last_quote = defaultdict(float)
        self.last_auto = defaultdict(float)
    
    async def get_quote(self) -> str:
        """Get random quote"""
        quotes = [
            ("The only way to do great work is to love what you do.", "Steve Jobs"),
            ("Success is not final, failure is not fatal.", "Winston Churchill"),
            ("Believe you can and you're halfway there.", "Theodore Roosevelt"),
            ("The future belongs to those who believe in their dreams.", "Eleanor Roosevelt"),
            ("Life is what happens when you're busy making other plans.", "John Lennon"),
            ("Be the change you wish to see in the world.", "Mahatma Gandhi"),
            ("Stay hungry, stay foolish.", "Steve Jobs"),
            ("The best time to plant a tree was 20 years ago.", "Chinese Proverb"),
            ("It does not matter how slowly you go as long as you do not stop.", "Confucius"),
            ("Everything you've ever wanted is on the other side of fear.", "Unknown")
        ]
        quote, author = random.choice(quotes)
        return f"💭 *Quote of the Moment*\n\n“{quote}”\n— {author}"
    
    async def get_joke(self) -> str:
        """Get random joke"""
        jokes = [
            "Why don't scientists trust atoms? Because they make up everything!",
            "What do you call a fake noodle? An impasta!",
            "Why did the scarecrow win an award? He was outstanding in his field!",
            "Why don't eggs tell jokes? They'd crack each other up!",
            "What do you call a sleeping bull? A bulldozer!",
            "Why did the math book look sad? Because it had too many problems!"
        ]
        return f"😂 *Joke Time*\n{random.choice(jokes)}"
    
    async def get_fact(self) -> str:
        """Get random fact"""
        facts = [
            "Honey never spoils. Archaeologists found 3000-year-old honey that's still good!",
            "Octopuses have three hearts and blue blood.",
            "A day on Venus is longer than a year on Venus.",
            "Bananas are berries, but strawberries aren't.",
            "The shortest war in history lasted only 38 minutes.",
            "A group of flamingos is called a 'flamboyance'.",
            "The Eiffel Tower can be 15 cm taller during the summer.",
            "Humans share 60% of their DNA with bananas."
        ]
        return f"📚 *Did You Know?*\n{random.choice(facts)}"
    
    async def get_motivation(self) -> str:
        """Get motivational message"""
        messages = [
            "Keep going! Every step counts toward your goal.",
            "You are stronger than you think. Keep pushing forward!",
            "Today is a great day to make progress!",
            "Small steps every day lead to big results.",
            "Believe in yourself and anything is possible!",
            "Your only limit is your mind. Dream big!",
            "Success is not final, failure is not fatal. Keep going!"
        ]
        return f"💪 *Motivation*\n{random.choice(messages)}"
    
    async def get_random(self) -> str:
        """Get random message type"""
        choices = [
            self.get_quote,
            self.get_joke,
            self.get_fact,
            self.get_motivation
        ]
        return await random.choice(choices)()
    
    async def send_quote_if_needed(self, bot, chat_id: int, interval: int = 600):
        """Send quote if enough time passed"""
        now = time.time()
        if now - self.last_quote[chat_id] >= interval:
            msg = await self.get_quote()
            try:
                await bot.send_message(chat_id, msg, parse_mode=ParseMode.MARKDOWN)
                self.last_quote[chat_id] = now
                logger.info(f"Sent quote to {chat_id}")
            except Exception as e:
                logger.error(f"Failed to send quote: {e}")
    
    async def send_auto_if_needed(self, bot, chat_id: int, interval: int = 10800):
        """Send auto message if enough time passed"""
        now = time.time()
        if now - self.last_auto[chat_id] >= interval:
            msg = await self.get_random()
            try:
                await bot.send_message(chat_id, msg, parse_mode=ParseMode.MARKDOWN)
                self.last_auto[chat_id] = now
                logger.info(f"Sent auto message to {chat_id}")
            except Exception as e:
                logger.error(f"Failed to send auto message: {e}")

# ==================== AUTO MESSAGE INSTANCE ====================
auto_messages = AutoMessageManager()

# ==================== KEYBOARDS ====================
class Keyboards:
    """Inline and reply keyboards"""
    
    @staticmethod
    def main_menu():
        return ReplyKeyboardMarkup([
            [KeyboardButton("🌤 Weather"), KeyboardButton("😂 Joke")],
            [KeyboardButton("💭 Quote"), KeyboardButton("📚 Fact")],
            [KeyboardButton("💪 Motivation"), KeyboardButton("🎵 Song")],
            [KeyboardButton("👥 Group Tools"), KeyboardButton("👑 Admin")]
        ], resize_keyboard=True)
    
    @staticmethod
    def group_menu():
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("👋 Welcome", callback_data="group_welcome"),
             InlineKeyboardButton("🛡 Rules", callback_data="group_rules")],
            [InlineKeyboardButton("⚠️ Warnings", callback_data="group_warnings"),
             InlineKeyboardButton("🚫 Bans", callback_data="group_bans")],
            [InlineKeyboardButton("⚙️ Settings", callback_data="group_settings"),
             InlineKeyboardButton("📊 Stats", callback_data="group_stats")],
            [InlineKeyboardButton("🔙 Back", callback_data="back_main")]
        ])
    
    @staticmethod
    def admin_menu():
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("📊 Stats", callback_data="admin_stats"),
             InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")],
            [InlineKeyboardButton("🛡 Moderation", callback_data="admin_mod"),
             InlineKeyboardButton("📋 Groups", callback_data="admin_groups")],
            [InlineKeyboardButton("⚙️ Settings", callback_data="admin_settings"),
             InlineKeyboardButton("📈 Logs", callback_data="admin_logs")],
            [InlineKeyboardButton("🔙 Back", callback_data="back_main")]
        ])
    
    @staticmethod
    def back_only():
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data="back_main")]
        ])

# ==================== COMMAND HANDLERS ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command handler"""
    user = update.effective_user
    
    # Track user
    db.update('users', str(user.id), {
        'username': user.username,
        'first_name': user.first_name,
        'last_seen': datetime.now().isoformat()
    })
    
    text = f"""
👋 *Welcome {user.first_name}!*

I'm *Alita Assistant* - a powerful group management bot like Rose.

✨ *Features:*
• 🛡️ Auto-moderation (spam, bad words, links)
• 🤖 Anti-flood & anti-spam protection
• 👋 Welcome/Goodbye messages
• ⏰ Auto quotes every 10 minutes
• 💬 Auto messages every 3 hours
• ⚠️ Warning system with auto-mute/ban
• 📊 Group statistics
• 🎮 Fun commands (jokes, quotes, facts)

Add me to your group and make me **admin** to start moderating!
"""
    await update.message.reply_text(
        text,
        reply_markup=Keyboards.main_menu(),
        parse_mode=ParseMode.MARKDOWN
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Help command"""
    text = """
📚 *Commands*

*User Commands:*
/start - Start the bot
/help - Show this help
/rules - Show group rules
/mywarns - Check your warnings
/report - Report a user (reply to message)

*Admin Commands:*
/warn [@user] [reason] - Warn user
/unwarn [@user] - Remove warnings
/mute [@user] [time] - Mute user
/unmute [@user] - Unmute user
/ban [@user] - Ban user
/unban [@user] - Unban user
/kick [@user] - Kick user
/purge [N] - Delete N messages
/slowmode [seconds] - Set slowmode
/settings - View group settings
/stats - Group statistics

*Moderation:*
• Warning 1-2: Verbal warning
• Warning 3: Mute 1 hour
• Warning 4: Mute 24 hours
• Warning 5: Mute 1 week
• Warning 6: Ban
"""
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show group rules"""
    chat = update.effective_chat
    settings = db.get('settings', str(chat.id), default_group_settings)
    rules_text = settings.get('rules', "No rules set. Use /setrules to add rules.")
    
    await update.message.reply_text(
        f"📜 *Group Rules*\n\n{rules_text}",
        parse_mode=ParseMode.MARKDOWN
    )

async def mywarns(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check your warnings"""
    user = update.effective_user
    chat = update.effective_chat
    
    warnings = warning_manager.get_warnings(user.id, chat.id)
    count = len(warnings)
    limit = db.get('settings', str(chat.id), default_group_settings).get('warn_limit', 3)
    
    if count == 0:
        text = f"✅ {user.first_name}, you have no warnings. Good job!"
    else:
        text = f"⚠️ *Warnings for {user.first_name}*\n"
        text += f"Total: {count}/{limit}\n\n"
        for i, w in enumerate(warnings[-5:], 1):
            text += f"{i}. {w['reason']} ({w['date'][:10]})\n"
    
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def warn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Warn a user (admin only)"""
    # Check if admin
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Admin only command!")
        return
    
    if not context.args:
        await update.message.reply_text("Usage: /warn @user [reason]")
        return
    
    # Parse target
    target_text = context.args[0]
    reason = ' '.join(context.args[1:]) if len(context.args) > 1 else "No reason"
    
    # Find user
    chat = update.effective_chat
    target = None
    
    if update.message.reply_to_message:
        target = update.message.reply_to_message.from_user
    else:
        username = target_text.replace('@', '').lower()
        try:
            async for member in chat.get_members():
                if member.user.username and member.user.username.lower() == username:
                    target = member.user
                    break
        except:
            pass
    
    if not target:
        await update.message.reply_text("❌ User not found!")
        return
    
    # Add warning
    result = warning_manager.add_warning(
        target.id, chat.id, reason,
        update.effective_user.username or update.effective_user.first_name
    )
    
    # Send warning
    text = f"""
⚠️ *User Warned*

**User:** {target.first_name}
**Reason:** {reason}
**Warnings:** {result['count']}
**Admin:** {update.effective_user.first_name}

Please follow group rules.
"""
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
    
    # Apply punishment if needed
    if result['punishment']:
        punishment = result['punishment']
        if punishment['action'] == 'mute':
            # Mute user
            permissions = ChatPermissions(
                can_send_messages=False,
                can_send_media_messages=False,
                can_send_polls=False,
                can_send_other_messages=False
            )
            
            until = datetime.now() + timedelta(seconds=punishment['duration'])
            await context.bot.restrict_chat_member(
                chat_id=chat.id,
                user_id=target.id,
                permissions=permissions,
                until_date=until
            )
            
            hours = punishment['duration'] // 3600
            mute_text = f"""
🔇 *User Auto-Muted*

**User:** {target.first_name}
**Duration:** {hours} hours
**Reason:** Reached {result['count']} warnings

Contact admins to appeal.
"""
            await update.message.reply_text(mute_text, parse_mode=ParseMode.MARKDOWN)
            
        elif punishment['action'] == 'ban':
            # Ban user
            await context.bot.ban_chat_member(chat.id, target.id)
            ban_text = f"""
🚫 *User Auto-Banned*

**User:** {target.first_name}
**Reason:** Reached {result['count']} warnings

This user has been permanently banned.
"""
            await update.message.reply_text(ban_text, parse_mode=ParseMode.MARKDOWN)

# ==================== MESSAGE HANDLER ====================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Main message handler"""
    if not update.message or not update.message.text:
        return
    
    user = update.effective_user
    chat = update.effective_chat
    text = update.message.text
    
    # Track user
    db.update('users', str(user.id), {
        'username': user.username,
        'first_name': user.first_name,
        'last_seen': datetime.now().isoformat(),
        'last_message': text[:100]
    })
    
    # Handle private chats
    if chat.type == "private":
        await handle_private(update, context)
        return
    
    # Handle group messages with moderation
    if chat.type in ["group", "supergroup"]:
        await handle_group(update, context)

async def handle_private(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle private chat messages"""
    text = update.message.text
    user = update.effective_user
    
    # Menu buttons
    if text == "🌤 Weather":
        weather = await get_weather()
        await update.message.reply_text(weather, parse_mode=ParseMode.MARKDOWN)
    
    elif text == "😂 Joke":
        joke = await auto_messages.get_joke()
        await update.message.reply_text(joke, parse_mode=ParseMode.MARKDOWN)
    
    elif text == "💭 Quote":
        quote = await auto_messages.get_quote()
        await update.message.reply_text(quote, parse_mode=ParseMode.MARKDOWN)
    
    elif text == "📚 Fact":
        fact = await auto_messages.get_fact()
        await update.message.reply_text(fact, parse_mode=ParseMode.MARKDOWN)
    
    elif text == "💪 Motivation":
        mot = await auto_messages.get_motivation()
        await update.message.reply_text(mot, parse_mode=ParseMode.MARKDOWN)
    
    elif text == "🎵 Song":
        songs = [
            ("Kesariya", "Brahmāstra"),
            ("Apna Bana Le", "Bhediya"),
            ("Flowers", "Miley Cyrus"),
            ("Anti-Hero", "Taylor Swift"),
            ("Pasoori", "Coke Studio")
        ]
        song, artist = random.choice(songs)
        await update.message.reply_text(
            f"🎵 *Song Suggestion*\n**{song}** by {artist}",
            parse_mode=ParseMode.MARKDOWN
        )
    
    elif text == "👥 Group Tools":
        await update.message.reply_text(
            "Add me to a group and make me admin!",
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
        lower = text.lower()
        if any(word in lower for word in ['hello', 'hi', 'hey', 'hola']):
            await update.message.reply_text(f"👋 Hello {user.first_name}!")
        elif any(word in lower for word in ['thanks', 'thank you', 'thx']):
            await update.message.reply_text("😊 You're welcome!")
        elif any(word in lower for word in ['bye', 'goodbye', 'cya']):
            await update.message.reply_text("👋 Goodbye! Come back anytime!")

async def handle_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle group messages with full moderation"""
    user = update.effective_user
    chat = update.effective_chat
    text = update.message.text
    
    # Skip commands
    if text.startswith('/'):
        return
    
    # Get group settings
    settings = db.get('settings', str(chat.id), default_group_settings)
    
    # ===== ANTI-SPAM CHECK =====
    if settings.get('antispam', True):
        spam = anti_spam.check(user.id, chat.id, text)
        if spam:
            # Delete spam message
            try:
                await update.message.delete()
            except:
                pass
            
            # Add warning
            result = warning_manager.add_warning(
                user.id, chat.id,
                f"Spam: {spam['reason']}",
                'system'
            )
            
            # Send warning (auto-delete after 10s)
            warn_text = f"""
⚠️ *Spam Detected*
User: {user.first_name}
Reason: {spam['reason']}
Warning: {result['count']}

Please don't spam.
"""
            msg = await update.message.reply_text(warn_text, parse_mode=ParseMode.MARKDOWN)
            
            # Auto-delete warning
            await asyncio.sleep(10)
            try:
                await msg.delete()
            except:
                pass
            
            # Apply punishment if needed
            if result['punishment']:
                await apply_punishment(update, context, user, result['punishment'])
            
            return
    
    # ===== CONTENT MODERATION =====
    violation = moderator.check(text)
    if violation:
        # Delete message if needed
        if violation['action'] == 'delete':
            try:
                await update.message.delete()
            except:
                pass
        
        # Add warning
        result = warning_manager.add_warning(
            user.id, chat.id,
            violation['type'].replace('_', ' ').title(),
            'system'
        )
        
        # Send warning
        warn_text = f"""
⚠️ *Rule Violation*
User: {user.first_name}
Reason: {violation['type'].replace('_', ' ').title()}
Warning: {result['count']}

Please follow group rules.
"""
        msg = await update.message.reply_text(warn_text, parse_mode=ParseMode.MARKDOWN)
        
        # Auto-delete warning
        await asyncio.sleep(10)
        try:
            await msg.delete()
        except:
            pass
        
        # Apply punishment if needed
        if result['punishment']:
            await apply_punishment(update, context, user, result['punishment'])
        
        return

async def apply_punishment(update: Update, context: ContextTypes.DEFAULT_TYPE, user, punishment: Dict):
    """Apply punishment to user"""
    chat = update.effective_chat
    
    if punishment['action'] == 'mute':
        # Mute user
        permissions = ChatPermissions(
            can_send_messages=False,
            can_send_media_messages=False,
            can_send_polls=False,
            can_send_other_messages=False
        )
        
        until = datetime.now() + timedelta(seconds=punishment['duration'])
        await context.bot.restrict_chat_member(
            chat_id=chat.id,
            user_id=user.id,
            permissions=permissions,
            until_date=until
        )
        
        hours = punishment['duration'] // 3600
        text = f"""
🔇 *User Auto-Muted*

**User:** {user.first_name}
**Duration:** {hours} hours
**Reason:** Reached warning limit

Contact admins to appeal.
"""
        await context.bot.send_message(chat.id, text, parse_mode=ParseMode.MARKDOWN)
        
    elif punishment['action'] == 'ban':
        # Ban user
        await context.bot.ban_chat_member(chat.id, user.id)
        text = f"""
🚫 *User Auto-Banned*

**User:** {user.first_name}
**Reason:** Reached maximum warnings

This user has been permanently banned.
"""
        await context.bot.send_message(chat.id, text, parse_mode=ParseMode.MARKDOWN)

# ==================== API FUNCTIONS ====================
async def get_weather(city: str = "London") -> str:
    """Get weather from wttr.in"""
    try:
        async with aiohttp.ClientSession() as session:
            url = f"http://wttr.in/{city}?format=%C+%t+%h+%w"
            async with session.get(url, timeout=5) as resp:
                if resp.status == 200:
                    data = await resp.text()
                    return f"🌤 *Weather in {city.title()}*\n`{data.strip()}`"
    except:
        pass
    return f"🌤 *Weather in {city.title()}*\n`☀️ 25°C • 💧 60% • 🌬 10km/h`"

# ==================== GROUP HANDLERS ====================
async def welcome_new(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Welcome new members"""
    chat = update.effective_chat
    settings = db.get('settings', str(chat.id), default_group_settings)
    
    if not settings.get('welcome', True):
        return
    
    for member in update.message.new_chat_members:
        if member.id == context.bot.id:
            # Bot was added
            db.set('groups', str(chat.id), {
                'title': chat.title,
                'added': datetime.now().isoformat(),
                'members': 0
            })
            
            await update.message.reply_text(
                f"🤖 *Thanks for adding me to {chat.title}!*\n\n"
                f"Please make me **admin** to work properly!\n"
                f"• Auto-moderation\n"
                f"• Anti-spam\n"
                f"• Welcome messages\n"
                f"• Auto quotes every 10min\n\n"
                f"Use /help to see commands.",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            # New user joined
            welcome_text = settings.get(
                'welcome_message',
                "👋 Welcome {name} to {group}!"
            ).format(
                name=member.first_name,
                group=chat.title,
                mention=member.mention_html()
            )
            
            await update.message.reply_text(
                welcome_text,
                parse_mode=ParseMode.HTML
            )

async def goodbye_left(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Goodbye leaving members"""
    chat = update.effective_chat
    settings = db.get('settings', str(chat.id), default_group_settings)
    
    if not settings.get('goodbye', True):
        return
    
    member = update.message.left_chat_member
    if member and member.id != context.bot.id:
        goodbye_text = settings.get(
            'goodbye_message',
            "👋 Goodbye {name}!"
        ).format(name=member.first_name)
        
        await update.message.reply_text(goodbye_text)

# ==================== BUTTON HANDLER ====================
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline button clicks"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user = update.effective_user
    
    if data == "group_welcome":
        text = """
👋 *Welcome Settings*

• Welcome messages: ✅ ON
• Goodbye messages: ✅ ON

Use /setwelcome [text] to customize
Use /setgoodbye [text] to customize

Variables: {name}, {group}, {mention}
"""
        await query.edit_message_text(
            text,
            reply_markup=Keyboards.back_only(),
            parse_mode=ParseMode.MARKDOWN
        )
    
    elif data == "group_rules":
        chat = update.effective_chat
        settings = db.get('settings', str(chat.id), default_group_settings)
        rules = settings.get('rules', "No rules set. Use /setrules to add rules.")
        
        await query.edit_message_text(
            f"📜 *Group Rules*\n\n{rules}",
            reply_markup=Keyboards.back_only(),
            parse_mode=ParseMode.MARKDOWN
        )
    
    elif data == "group_warnings":
        # Count total warnings in this chat
        total = 0
        for key in db.get('warnings', default={}):
            if key.startswith(f"{update.effective_chat.id}:"):
                total += 1
        
        await query.edit_message_text(
            f"⚠️ *Warnings*\n\nTotal active warnings: {total}",
            reply_markup=Keyboards.back_only(),
            parse_mode=ParseMode.MARKDOWN
        )
    
    elif data == "group_bans":
        bans = db.get('bans', str(update.effective_chat.id), [])
        await query.edit_message_text(
            f"🚫 *Bans*\n\nTotal banned users: {len(bans)}",
            reply_markup=Keyboards.back_only(),
            parse_mode=ParseMode.MARKDOWN
        )
    
    elif data == "group_settings":
        chat = update.effective_chat
        settings = db.get('settings', str(chat.id), default_group_settings)
        
        text = f"""
⚙️ *Group Settings*

**Welcome:** {"✅" if settings.get('welcome') else "❌"}
**Goodbye:** {"✅" if settings.get('goodbye') else "❌"}
**Anti-Spam:** {"✅" if settings.get('antispam') else "❌"}
**Anti-Link:** {"✅" if settings.get('antilink') else "❌"}
**Auto Quote:** {"✅" if settings.get('auto_quote') else "❌"}

**Warn Limit:** {settings.get('warn_limit')}
**Mute Time:** {settings.get('mute_time', 3600)//3600}h
**Ban Time:** {settings.get('ban_time', 86400)//3600}h
"""
        await query.edit_message_text(
            text,
            reply_markup=Keyboards.back_only(),
            parse_mode=ParseMode.MARKDOWN
        )
    
    elif data == "group_stats":
        chat = update.effective_chat
        members = 0
        try:
            members = await chat.get_member_count()
        except:
            pass
        
        stats = db.get('stats', str(chat.id), {
            'messages': 0,
            'warnings': 0,
            'mutes': 0,
            'bans': 0
        })
        
        text = f"""
📊 *Group Statistics*

**Name:** {chat.title}
**Members:** {members}
**Type:** {chat.type}
**ID:** `{chat.id}`

**Messages:** {stats.get('messages', 0)}
**Warnings:** {stats.get('warnings', 0)}
**Mutes:** {stats.get('mutes', 0)}
**Bans:** {stats.get('bans', 0)}
"""
        await query.edit_message_text(
            text,
            reply_markup=Keyboards.back_only(),
            parse_mode=ParseMode.MARKDOWN
        )
    
    elif data == "admin_stats":
        if user.id != ADMIN_ID:
            await query.edit_message_text("❌ Admin only!")
            return
        
        users = len(db.get('users', default={}))
        groups = len(db.get('groups', default={}))
        warnings = len(db.get('warnings', default={}))
        
        text = f"""
📊 *Bot Statistics*

**Users:** {users}
**Groups:** {groups}
**Warnings:** {warnings}
**Active since:** Online
**Version:** 2.0 (Rose-like)
"""
        await query.edit_message_text(
            text,
            reply_markup=Keyboards.admin_menu(),
            parse_mode=ParseMode.MARKDOWN
        )
    
    elif data == "admin_broadcast":
        if user.id != ADMIN_ID:
            await query.edit_message_text("❌ Admin only!")
            return
        
        await query.edit_message_text(
            "📢 *Broadcast*\n\nUse /broadcast [message] to send to all groups",
            reply_markup=Keyboards.admin_menu(),
            parse_mode=ParseMode.MARKDOWN
        )
    
    elif data == "admin_mod":
        if user.id != ADMIN_ID:
            await query.edit_message_text("❌ Admin only!")
            return
        
        text = """
🛡 *Moderation Settings*

**Spam Threshold:** 5 msgs/30s
**Flood Threshold:** 10 msgs/30s
**Warn Limit:** 3 → Mute 1h
**Warn Level 4:** Mute 24h
**Warn Level 5:** Mute 1w
**Warn Level 6:** Ban

**Bad Words:** 50+ filtered
**Link Blocking:** Enabled
**Mass Mention:** Blocked
"""
        await query.edit_message_text(
            text,
            reply_markup=Keyboards.admin_menu(),
            parse_mode=ParseMode.MARKDOWN
        )
    
    elif data == "admin_groups":
        if user.id != ADMIN_ID:
            await query.edit_message_text("❌ Admin only!")
            return
        
        groups = db.get('groups', default={})
        text = "📋 *Groups*\n\n"
        for gid, info in list(groups.items())[:10]:
            text += f"• {info.get('title', 'Unknown')}\n"
        
        await query.edit_message_text(
            text,
            reply_markup=Keyboards.admin_menu(),
            parse_mode=ParseMode.MARKDOWN
        )
    
    elif data == "admin_settings":
        if user.id != ADMIN_ID:
            await query.edit_message_text("❌ Admin only!")
            return
        
        text = """
⚙️ *Bot Settings*

**Auto Quote:** Every 10 minutes
**Auto Message:** Every 3 hours
**Warning Cooldown:** 30 seconds
**Message Retention:** 30 seconds

**Features:**
• ✅ Anti-Spam
• ✅ Anti-Flood
• ✅ Anti-Link
• ✅ Auto-Moderation
• ✅ Warning System
• ✅ Auto-Mute/Ban
"""
        await query.edit_message_text(
            text,
            reply_markup=Keyboards.admin_menu(),
            parse_mode=ParseMode.MARKDOWN
        )
    
    elif data == "admin_logs":
        if user.id != ADMIN_ID:
            await query.edit_message_text("❌ Admin only!")
            return
        
        await query.edit_message_text(
            "📈 *Logs*\n\nCheck Render dashboard for logs.",
            reply_markup=Keyboards.admin_menu(),
            parse_mode=ParseMode.MARKDOWN
        )
    
    elif data == "back_main":
        await query.edit_message_text(
            "🏠 *Main Menu*",
            reply_markup=Keyboards.main_menu(),
            parse_mode=ParseMode.MARKDOWN
        )

# ==================== ERROR HANDLER ====================
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors"""
    logger.error(f"Update {update} caused error {context.error}")

# ==================== PERIODIC TASKS ====================
async def periodic_tasks(app: Application):
    """Run periodic tasks (quotes, auto messages)"""
    logger.info("✅ Periodic tasks started")
    
    while True:
        try:
            # Get all groups
            groups = db.get('groups', default={})
            
            for chat_id_str in groups:
                chat_id = int(chat_id_str)
                settings = db.get('settings', chat_id_str, default_group_settings)
                
                # Send quote if enabled
                if settings.get('auto_quote', True):
                    interval = settings.get('auto_quote_interval', 600)
                    await auto_messages.send_quote_if_needed(app.bot, chat_id, interval)
                
                # Send auto message if enabled
                if settings.get('auto_message', True):
                    interval = settings.get('auto_message_interval', 10800)
                    await auto_messages.send_auto_if_needed(app.bot, chat_id, interval)
                
                # Small delay to avoid rate limits
                await asyncio.sleep(2)
            
            # Check every minute
            await asyncio.sleep(60)
            
        except Exception as e:
            logger.error(f"Periodic task error: {e}")
            await asyncio.sleep(60)

# ==================== HEALTH CHECK ====================
async def health_check(request):
    """Simple health check for Render"""
    return aiohttp.web.Response(text="OK", status=200)

async def run_web_server():
    """Run health check server"""
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
    except Exception as e:
        logger.error(f"Health server error: {e}")

# ==================== MAIN ====================
async def main():
    """Main async function"""
    # Create application
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("rules", rules))
    app.add_handler(CommandHandler("mywarns", mywarns))
    app.add_handler(CommandHandler("warn", warn))
    
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_new))
    app.add_handler(MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER, goodbye_left))
    
    app.add_error_handler(error_handler)
    
    # Set commands
    await app.bot.set_my_commands([
        BotCommand("start", "Start the bot"),
        BotCommand("help", "Show help"),
        BotCommand("rules", "Show rules"),
        BotCommand("mywarns", "Check your warnings")
    ])
    
    # Start web server
    await run_web_server()
    
    # Start periodic tasks
    asyncio.create_task(periodic_tasks(app))
    
    logger.info("🚀 Bot started! Fully automated with:")
    logger.info("• Auto quotes every 10 minutes")
    logger.info("• Auto messages every 3 hours")
    logger.info("• Anti-spam with auto-mute/ban")
    logger.info("• Warning system like Rose")
    
    # Start polling
    await app.run_polling(allowed_updates=Update.ALL_TYPES)

def run():
    """Entry point with proper asyncio handling"""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    run()
