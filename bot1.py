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
import sys
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union

import aiohttp
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton, BotCommand, ChatPermissions,
    User, Chat
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)

# ==================== CONFIGURATION ====================
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Your bot token - CHANGE THIS TO YOUR BOT TOKEN
BOT_TOKEN = "8168577329:AAFgYEHmIe-SDuRL3tqt6rx1MtAnJprSbRc"  # Replace with your actual bot token
ADMIN_ID = 7327016053   # Replace with your admin ID

# ==================== DATA MANAGEMENT ====================
class Database:
    """Simple JSON-based database with auto-save"""
    
    def __init__(self):
        self.data_files = {
            'users': 'users.json',
            'groups': 'groups.json',
            'warnings': 'warnings.json',
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
                    with open(file, 'r', encoding='utf-8') as f:
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
            with open(self.data_files[name], 'w', encoding='utf-8') as f:
                json.dump(self.data[name], f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving {self.data_files[name]}: {e}")
    
    def get(self, name: str, key: str = None, default=None):
        """Get data"""
        if key is not None:
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
DEFAULT_GROUP_SETTINGS = {
    'welcome': True,
    'goodbye': True,
    'antispam': True,
    'antiflood': True,
    'antilink': True,
    'warn_limit': 3,
    'mute_time': 3600,
    'ban_time': 86400,
    'auto_quote': True,
    'auto_quote_interval': 600,
    'auto_message': True,
    'auto_message_interval': 10800,
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
        self.action_cooldown = 30
    
    def check(self, user_id: int, chat_id: int, text: str) -> Optional[Dict]:
        """Check if message is spam. Returns None or violation dict."""
        now = time.time()
        key = f"{chat_id}:{user_id}"
        
        self.message_history[key].append({
            'text': text,
            'time': now
        })
        
        if now - self.last_action[key] < self.action_cooldown:
            return None
        
        recent = [m for m in self.message_history[key] if now - m['time'] < 30]
        
        if len(recent) >= 10:
            self.spam_count[key] += 1
            self.last_action[key] = now
            return {
                'type': 'flood',
                'reason': f"{len(recent)} messages in 30s",
                'severity': self.spam_count[key]
            }
        
        if len(recent) >= 5:
            texts = [m['text'] for m in recent if m['text']]
            if len(set(texts)) <= 2:
                self.spam_count[key] += 1
                self.last_action[key] = now
                return {
                    'type': 'spam',
                    'reason': f"{len(recent)} repeated messages",
                    'severity': self.spam_count[key]
                }
        
        if text and len(text) > 20 and len(set(text)) < 5:
            self.spam_count[key] += 1
            self.last_action[key] = now
            return {
                'type': 'keyboard_spam',
                'reason': "Repeated characters",
                'severity': self.spam_count[key]
            }
        
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
            'chutiya', 'madarchod', 'bhenchod', 'lund', 'gandu', 'randi'
        ]
        
        self.custom_filters = db.get('filters', 'words', [])
    
    def check(self, text: str) -> Optional[Dict]:
        """Check message for violations. Returns None or violation dict."""
        if not text:
            return None
            
        text_lower = text.lower()
        
        # Check bad words
        for word in self.bad_words + self.custom_filters:
            if word in text_lower:
                return {
                    'type': 'bad_word',
                    'word': word,
                    'action': 'delete'
                }
        
        # Check excessive caps
        if len(text) > 10:
            caps = sum(1 for c in text if c.isupper())
            if caps / len(text) > 0.7:  # Increased threshold to 70%
                return {
                    'type': 'excessive_caps',
                    'action': 'warn'
                }
        
        # Check links if antilink is enabled
        if re.search(r'https?://|www\.|t\.me/|telegram\.me/|discord\.gg', text_lower):
            return {
                'type': 'link',
                'action': 'delete'
            }
        
        # Check mass mentions
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
            3: {'action': 'mute', 'duration': 3600},
            4: {'action': 'mute', 'duration': 86400},
            5: {'action': 'mute', 'duration': 604800},
            6: {'action': 'ban', 'duration': 0}
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
        return db.delete('warnings', key)
    
    def get_warning_count(self, user_id: int, chat_id: int) -> int:
        """Get warning count for user"""
        return len(self.get_warnings(user_id, chat_id))

# Initialize managers
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
            ("The best way to predict the future is to create it.", "Peter Drucker"),
            ("It does not matter how slowly you go as long as you do not stop.", "Confucius"),
            ("Everything you've ever wanted is on the other side of fear.", "George Addair")
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
            "Why don't skeletons fight each other? They don't have the guts!",
            "What do you call a bear with no teeth? A gummy bear!",
            "Why did the math book look sad? Because it had too many problems!"
        ]
        return f"😂 *Joke Time*\n\n{random.choice(jokes)}"
    
    async def get_fact(self) -> str:
        """Get random fact"""
        facts = [
            "Honey never spoils. Archaeologists found 3000-year-old honey that's still good!",
            "Octopuses have three hearts and blue blood.",
            "A day on Venus is longer than a year on Venus.",
            "Bananas are berries, but strawberries aren't.",
            "The shortest war in history lasted only 38 minutes.",
            "A group of flamingos is called a 'flamboyance'.",
            "The Eiffel Tower can be 15 cm taller during the summer due to thermal expansion.",
            "Cows have best friends and get stressed when separated from them.",
            "The human nose can detect over 1 trillion different scents."
        ]
        return f"📚 *Did You Know?*\n\n{random.choice(facts)}"
    
    async def get_motivation(self) -> str:
        """Get motivational message"""
        messages = [
            "Keep going! Every step counts toward your goal.",
            "You are stronger than you think. Keep pushing forward!",
            "Today is a great day to make progress!",
            "Small steps every day lead to big results.",
            "Believe in yourself and anything is possible!",
            "Your only limit is your mind.",
            "Don't watch the clock; do what it does. Keep going.",
            "The future depends on what you do today."
        ]
        return f"💪 *Motivation*\n\n{random.choice(messages)}"
    
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
                logger.info(f"Sent quote to chat {chat_id}")
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
                logger.info(f"Sent auto message to chat {chat_id}")
            except Exception as e:
                logger.error(f"Failed to send auto message: {e}")

# Initialize auto messages
auto_messages = AutoMessageManager()

# ==================== KEYBOARDS ====================
class Keyboards:
    """Inline and reply keyboards"""
    
    @staticmethod
    def main_menu():
        """Main menu keyboard"""
        keyboard = [
            [KeyboardButton("🌤 Weather"), KeyboardButton("😂 Joke")],
            [KeyboardButton("💭 Quote"), KeyboardButton("📚 Fact")],
            [KeyboardButton("💪 Motivation"), KeyboardButton("👑 Admin")]
        ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    @staticmethod
    def group_menu():
        """Group management menu"""
        keyboard = [
            [InlineKeyboardButton("👋 Welcome", callback_data="group_welcome"),
             InlineKeyboardButton("🛡 Rules", callback_data="group_rules")],
            [InlineKeyboardButton("⚠️ Warnings", callback_data="group_warnings"),
             InlineKeyboardButton("🚫 Bans", callback_data="group_bans")],
            [InlineKeyboardButton("⚙️ Settings", callback_data="group_settings"),
             InlineKeyboardButton("📊 Stats", callback_data="group_stats")],
            [InlineKeyboardButton("🔙 Back", callback_data="back_main")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def admin_menu():
        """Admin menu keyboard"""
        keyboard = [
            [InlineKeyboardButton("📊 Stats", callback_data="admin_stats"),
             InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")],
            [InlineKeyboardButton("🛡 Moderation", callback_data="admin_mod"),
             InlineKeyboardButton("📋 Groups", callback_data="admin_groups")],
            [InlineKeyboardButton("⚙️ Settings", callback_data="admin_settings"),
             InlineKeyboardButton("📈 Logs", callback_data="admin_logs")],
            [InlineKeyboardButton("🔙 Back", callback_data="back_main")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def back_only():
        """Back button only"""
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="back_main")]]
        return InlineKeyboardMarkup(keyboard)

# ==================== COMMAND HANDLERS ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command handler"""
    user = update.effective_user
    
    # Update user in database
    db.update('users', str(user.id), {
        'username': user.username,
        'first_name': user.first_name,
        'last_seen': datetime.now().isoformat()
    })
    
    text = f"""
👋 *Welcome {user.first_name}!*

I'm *Alita Assistant* - a powerful group management bot like Rose.

✨ *Features:*
• 🛡️ Auto-moderation
• 🤖 Anti-flood & anti-spam
• 👋 Welcome/Goodbye messages
• ⏰ Auto quotes every 10 minutes
• ⚠️ Warning system with auto-mute/ban
• 📊 Group statistics
• 🎮 Fun commands

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

*Admin Commands:*
/warn @user [reason] - Warn user
/mute @user - Mute user
/unmute @user - Unmute user
/ban @user - Ban user
/unban @user - Unban user
/kick @user - Kick user
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
    
    if chat.type == "private":
        await update.message.reply_text("This command only works in groups!")
        return
        
    settings = db.get('settings', str(chat.id), DEFAULT_GROUP_SETTINGS)
    rules_text = settings.get('rules', "No rules set. Use /setrules to add rules.")
    
    await update.message.reply_text(
        f"📜 *Group Rules*\n\n{rules_text}",
        parse_mode=ParseMode.MARKDOWN
    )

async def mywarns(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check your warnings"""
    user = update.effective_user
    chat = update.effective_chat
    
    if chat.type == "private":
        await update.message.reply_text("This command only works in groups!")
        return
    
    warnings = warning_manager.get_warnings(user.id, chat.id)
    count = len(warnings)
    
    if count == 0:
        text = f"✅ {user.first_name}, you have no warnings. Good job!"
    else:
        text = f"⚠️ *Warnings for {user.first_name}*\n"
        text += f"Total: {count}\n\n"
        for i, w in enumerate(warnings[-5:], 1):
            # Format date nicely
            date = datetime.fromisoformat(w['date']).strftime('%Y-%m-%d')
            text += f"{i}. {w['reason']} ({date})\n"
    
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def warn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Warn a user (admin only)"""
    user_id = update.effective_user.id
    
    # Check if user is admin
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ Admin only command!")
        return
    
    chat = update.effective_chat
    
    if chat.type == "private":
        await update.message.reply_text("This command only works in groups!")
        return
    
    # Parse arguments
    if not context.args and not update.message.reply_to_message:
        await update.message.reply_text("Usage: /warn @user [reason] or reply to a message with /warn [reason]")
        return
    
    target = None
    reason = "No reason provided"
    
    if update.message.reply_to_message:
        target = update.message.reply_to_message.from_user
        if context.args:
            reason = ' '.join(context.args)
    else:
        # Try to get target from args
        target_text = context.args[0]
        reason = ' '.join(context.args[1:]) if len(context.args) > 1 else "No reason provided"
        
        # Try to find user by username
        username = target_text.replace('@', '').lower()
        
        try:
            # Get chat administrators
            admins = await context.bot.get_chat_administrators(chat.id)
            for admin in admins:
                if admin.user.username and admin.user.username.lower() == username:
                    target = admin.user
                    break
        except:
            pass
        
        # If not found, try to get by user_id
        if not target and target_text.lstrip('-').isdigit():
            try:
                user_id = int(target_text)
                # Try to get chat member
                member = await context.bot.get_chat_member(chat.id, user_id)
                target = member.user
            except:
                pass
    
    if not target:
        await update.message.reply_text("❌ User not found!")
        return
    
    # Don't warn admins
    if target.id == ADMIN_ID or target.id == context.bot.id:
        await update.message.reply_text("❌ Cannot warn this user!")
        return
    
    # Add warning
    admin_name = update.effective_user.username or update.effective_user.first_name
    result = warning_manager.add_warning(
        target.id, chat.id, reason, admin_name
    )
    
    text = f"""
⚠️ *User Warned*

**User:** {target.first_name} {f'(@{target.username})' if target.username else ''}
**Reason:** {reason}
**Warnings:** {result['count']}
**Admin:** {admin_name}

Please follow group rules.
"""
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
    
    # Apply punishment if needed
    if result['punishment']:
        await apply_punishment(update, context, target, result['punishment'], reason)

# ==================== MESSAGE HANDLER ====================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Main message handler"""
    if not update.message or not update.message.text:
        return
    
    user = update.effective_user
    chat = update.effective_chat
    text = update.message.text
    
    # Update user in database
    db.update('users', str(user.id), {
        'username': user.username,
        'first_name': user.first_name,
        'last_seen': datetime.now().isoformat()
    })
    
    # Update stats
    stats_key = str(chat.id) if chat.type != "private" else "private"
    stats = db.get('stats', stats_key, {'messages': 0})
    stats['messages'] = stats.get('messages', 0) + 1
    db.set('stats', stats_key, stats)
    
    if chat.type == "private":
        await handle_private(update, context)
    elif chat.type in ["group", "supergroup"]:
        await handle_group(update, context)

async def handle_private(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle private chat messages"""
    text = update.message.text
    user = update.effective_user
    
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
        lower = text.lower()
        if any(word in lower for word in ['hello', 'hi', 'hey']):
            await update.message.reply_text(f"👋 Hello {user.first_name}!")
        elif any(word in lower for word in ['thanks', 'thank you']):
            await update.message.reply_text("😊 You're welcome!")
        elif any(word in lower for word in ['bye', 'goodbye']):
            await update.message.reply_text(f"👋 Goodbye {user.first_name}!")

async def handle_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle group messages with full moderation"""
    user = update.effective_user
    chat = update.effective_chat
    message = update.message
    text = message.text
    
    # Ignore commands
    if text.startswith('/'):
        return
    
    # Don't moderate admins
    try:
        chat_member = await context.bot.get_chat_member(chat.id, user.id)
        if chat_member.status in ['administrator', 'creator']:
            return
    except:
        pass
    
    # Get group settings
    settings = db.get('settings', str(chat.id), DEFAULT_GROUP_SETTINGS)
    
    # Anti-spam check
    if settings.get('antispam', True):
        spam = anti_spam.check(user.id, chat.id, text)
        if spam:
            try:
                await message.delete()
            except Exception as e:
                logger.error(f"Could not delete spam message: {e}")
            
            # Add warning
            result = warning_manager.add_warning(
                user.id, chat.id,
                f"Spam: {spam['reason']}",
                'system'
            )
            
            warn_text = f"""
⚠️ *Spam Detected*
User: {user.first_name}
Reason: {spam['reason']}
Warning: {result['count']}/6

Please don't spam.
"""
            msg = await message.reply_text(warn_text, parse_mode=ParseMode.MARKDOWN)
            
            # Auto-delete warning after 10 seconds
            await asyncio.sleep(10)
            try:
                await msg.delete()
            except:
                pass
            
            # Apply punishment if needed
            if result['punishment']:
                await apply_punishment(update, context, user, result['punishment'], spam['reason'])
            
            return
    
    # Content moderation check
    if text:
        violation = moderator.check(text)
        if violation:
            if violation['action'] == 'delete':
                try:
                    await message.delete()
                except:
                    pass
            
            # Add warning
            result = warning_manager.add_warning(
                user.id, chat.id,
                violation['type'].replace('_', ' ').title(),
                'system'
            )
            
            warn_text = f"""
⚠️ *Rule Violation*
User: {user.first_name}
Reason: {violation['type'].replace('_', ' ').title()}
Warning: {result['count']}/6

Please follow group rules.
"""
            msg = await message.reply_text(warn_text, parse_mode=ParseMode.MARKDOWN)
            
            # Auto-delete warning after 10 seconds
            await asyncio.sleep(10)
            try:
                await msg.delete()
            except:
                pass
            
            # Apply punishment if needed
            if result['punishment']:
                await apply_punishment(update, context, user, result['punishment'], violation['type'])
            
            return

async def apply_punishment(update: Update, context: ContextTypes.DEFAULT_TYPE, 
                          user: User, punishment: Dict, reason: str):
    """Apply punishment to user"""
    chat = update.effective_chat
    
    try:
        if punishment['action'] == 'mute':
            # Create mute permissions
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
            
            # Set mute duration
            until = datetime.now() + timedelta(seconds=punishment['duration'])
            
            await context.bot.restrict_chat_member(
                chat_id=chat.id,
                user_id=user.id,
                permissions=permissions,
                until_date=until
            )
            
            # Format duration
            if punishment['duration'] < 3600:
                duration_str = f"{punishment['duration']//60} minutes"
            elif punishment['duration'] < 86400:
                duration_str = f"{punishment['duration']//3600} hours"
            else:
                duration_str = f"{punishment['duration']//86400} days"
            
            text = f"""
🔇 *User Auto-Muted*

**User:** {user.first_name} {f'(@{user.username})' if user.username else ''}
**Duration:** {duration_str}
**Reason:** {reason}
**Warnings:** {warning_manager.get_warning_count(user.id, chat.id)}/6

Please follow group rules.
"""
            await context.bot.send_message(chat.id, text, parse_mode=ParseMode.MARKDOWN)
            
            # Update stats
            stats = db.get('stats', str(chat.id), {})
            stats['mutes'] = stats.get('mutes', 0) + 1
            db.set('stats', str(chat.id), stats)
            
        elif punishment['action'] == 'ban':
            await context.bot.ban_chat_member(chat.id, user.id)
            
            text = f"""
🚫 *User Auto-Banned*

**User:** {user.first_name} {f'(@{user.username})' if user.username else ''}
**Reason:** {reason} (Reached maximum warnings)
"""
            await context.bot.send_message(chat.id, text, parse_mode=ParseMode.MARKDOWN)
            
            # Update stats
            stats = db.get('stats', str(chat.id), {})
            stats['bans'] = stats.get('bans', 0) + 1
            db.set('stats', str(chat.id), stats)
            
            # Store ban record
            bans = db.get('bans', str(chat.id), [])
            bans.append({
                'user_id': user.id,
                'username': user.username,
                'first_name': user.first_name,
                'reason': reason,
                'date': datetime.now().isoformat()
            })
            db.set('bans', str(chat.id), bans)
            
    except Exception as e:
        logger.error(f"Failed to apply punishment: {e}")

# ==================== API FUNCTIONS ====================
async def get_weather(city: str = "London") -> str:
    """Get weather from wttr.in"""
    try:
        async with aiohttp.ClientSession() as session:
            url = f"https://wttr.in/{city}?format=%C+%t+%h+%w"
            async with session.get(url, timeout=5) as resp:
                if resp.status == 200:
                    data = await resp.text()
                    return f"🌤 *Weather in {city.title()}*\n`{data.strip()}`"
    except Exception as e:
        logger.error(f"Weather API error: {e}")
    
    # Fallback weather data
    conditions = ["☀️ Sunny", "⛅ Partly Cloudy", "☁️ Cloudy", "🌧 Rainy", "⛈ Stormy"]
    temps = [f"{random.randint(15, 35)}°C", f"{random.randint(60, 85)}°F"]
    humidities = [f"{random.randint(40, 90)}%", f"{random.randint(40, 90)}%"]
    winds = [f"{random.randint(5, 25)}km/h", f"{random.randint(3, 15)}mph"]
    
    return f"🌤 *Weather in {city.title()}*\n`{random.choice(conditions)} • {random.choice(temps)} • 💧 {random.choice(humidities)} • 🌬 {random.choice(winds)}`"

# ==================== GROUP HANDLERS ====================
async def welcome_new(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Welcome new members"""
    if not update.message or not update.message.new_chat_members:
        return
        
    chat = update.effective_chat
    settings = db.get('settings', str(chat.id), DEFAULT_GROUP_SETTINGS)
    
    if not settings.get('welcome', True):
        return
    
    for member in update.message.new_chat_members:
        if member.id == context.bot.id:
            # Bot was added to group
            db.set('groups', str(chat.id), {
                'title': chat.title,
                'added': datetime.now().isoformat(),
                'members': 0
            })
            
            await update.message.reply_text(
                f"🤖 *Thanks for adding me to {chat.title}!*\n\n"
                f"Please make me **admin** to work properly!\n"
                f"Use /help to see commands.",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            # New user joined
            # Don't welcome bots
            if member.is_bot:
                continue
                
            welcome_text = settings.get(
                'welcome_message',
                "👋 Welcome {name} to {group}!"
            ).format(
                name=member.first_name,
                group=chat.title
            )
            
            await update.message.reply_text(
                welcome_text,
                parse_mode=ParseMode.MARKDOWN
            )

async def goodbye_left(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Goodbye leaving members"""
    if not update.message or not update.message.left_chat_member:
        return
        
    chat = update.effective_chat
    settings = db.get('settings', str(chat.id), DEFAULT_GROUP_SETTINGS)
    
    if not settings.get('goodbye', True):
        return
    
    member = update.message.left_chat_member
    if member and member.id != context.bot.id and not member.is_bot:
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
    chat = update.effective_chat
    
    if data == "group_welcome":
        chat_id = str(chat.id) if chat else "unknown"
        settings = db.get('settings', chat_id, DEFAULT_GROUP_SETTINGS)
        
        text = f"""
👋 *Welcome Settings*

• Welcome messages: {'✅ ON' if settings.get('welcome') else '❌ OFF'}
• Goodbye messages: {'✅ ON' if settings.get('goodbye') else '❌ OFF'}

Use /setwelcome [text] to customize
Use /setgoodbye [text] to customize

Variables: {{name}}, {{group}}

Current welcome: `{settings.get('welcome_message')}`
Current goodbye: `{settings.get('goodbye_message')}`
"""
        await query.edit_message_text(
            text,
            reply_markup=Keyboards.back_only(),
            parse_mode=ParseMode.MARKDOWN
        )
    
    elif data == "group_rules":
        chat_id = str(chat.id) if chat else "unknown"
        settings = db.get('settings', chat_id, DEFAULT_GROUP_SETTINGS)
        rules = settings.get('rules', "No rules set. Use /setrules to add rules.")
        
        await query.edit_message_text(
            f"📜 *Group Rules*\n\n{rules}",
            reply_markup=Keyboards.back_only(),
            parse_mode=ParseMode.MARKDOWN
        )
    
    elif data == "group_warnings":
        chat_id = str(chat.id) if chat else "unknown"
        total = 0
        warnings_data = db.get('warnings', default={})
        if warnings_data:
            for key in warnings_data:
                if key.startswith(f"{chat_id}:"):
                    total += 1
        
        await query.edit_message_text(
            f"⚠️ *Warnings*\n\nTotal active warnings: {total}",
            reply_markup=Keyboards.back_only(),
            parse_mode=ParseMode.MARKDOWN
        )
    
    elif data == "group_bans":
        chat_id = str(chat.id) if chat else "unknown"
        bans = db.get('bans', chat_id, [])
        
        if bans:
            text = f"🚫 *Bans*\n\nTotal banned users: {len(bans)}\n\n"
            for i, ban in enumerate(bans[-5:], 1):
                date = datetime.fromisoformat(ban['date']).strftime('%Y-%m-%d')
                text += f"{i}. {ban['first_name']} - {date}\n"
        else:
            text = "🚫 *Bans*\n\nNo banned users."
        
        await query.edit_message_text(
            text,
            reply_markup=Keyboards.back_only(),
            parse_mode=ParseMode.MARKDOWN
        )
    
    elif data == "group_settings":
        chat_id = str(chat.id) if chat else "unknown"
        settings = db.get('settings', chat_id, DEFAULT_GROUP_SETTINGS)
        
        text = f"""
⚙️ *Group Settings*

**Welcome:** {'✅' if settings.get('welcome') else '❌'}
**Goodbye:** {'✅' if settings.get('goodbye') else '❌'}
**Anti-Spam:** {'✅' if settings.get('antispam') else '❌'}
**Anti-Link:** {'✅' if settings.get('antilink') else '❌'}
**Auto Quote:** {'✅' if settings.get('auto_quote') else '❌'}

**Warn Limit:** {settings.get('warn_limit')}
**Mute Time:** {settings.get('mute_time', 3600)//3600}h
**Ban Time:** {settings.get('ban_time', 86400)//86400}d
"""
        await query.edit_message_text(
            text,
            reply_markup=Keyboards.back_only(),
            parse_mode=ParseMode.MARKDOWN
        )
    
    elif data == "group_stats":
        chat_id = str(chat.id) if chat else "unknown"
        members = 0
        try:
            if chat:
                members = await chat.get_member_count()
        except:
            pass
        
        stats = db.get('stats', chat_id, {
            'messages': 0,
            'warnings': 0,
            'mutes': 0,
            'bans': 0
        })
        
        text = f"""
📊 *Group Statistics*

**Name:** {chat.title if chat else 'Unknown'}
**Members:** {members}
**ID:** `{chat_id}`

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
        
        # Calculate total messages
        total_msgs = 0
        stats_data = db.get('stats', default={})
        for stat in stats_data.values():
            if isinstance(stat, dict):
                total_msgs += stat.get('messages', 0)
        
        text = f"""
📊 *Bot Statistics*

**Users:** {users}
**Groups:** {groups}
**Warnings:** {warnings}
**Messages:** {total_msgs}
**Version:** 2.0
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
            "📢 *Broadcast*\n\nUse /broadcast [message] to send to all groups\n\n"
            "Example: /broadcast Hello everyone!",
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

**Bad Words:** 20+ words filtered
**Link Detection:** ✅ Enabled
**Mass Mention:** ✅ Blocked
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
        
        if groups:
            text = "📋 *Groups*\n\n"
            for gid, info in list(groups.items())[:10]:
                title = info.get('title', 'Unknown')
                added = info.get('added', '')[:10] if info.get('added') else ''
                text += f"• {title} (`{gid}`) - {added}\n"
            
            if len(groups) > 10:
                text += f"\n... and {len(groups) - 10} more"
        else:
            text = "📋 *Groups*\n\nNo groups yet."
        
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

**Features:**
• ✅ Anti-Spam
• ✅ Anti-Flood
• ✅ Auto-Moderation
• ✅ Warning System
• ✅ Welcome/Goodbye
• ✅ Statistics
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
            "📈 *Logs*\n\nCheck console for detailed logs.\n\n"
            "Recent actions are logged to console with timestamps.",
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
    
    try:
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "❌ An error occurred. Please try again later."
            )
    except:
        pass

# ==================== PERIODIC TASKS ====================
async def periodic_tasks(app: Application):
    """Run periodic tasks"""
    logger.info("✅ Periodic tasks started")
    
    while True:
        try:
            groups = db.get('groups', default={})
            
            for chat_id_str in groups:
                try:
                    chat_id = int(chat_id_str)
                    settings = db.get('settings', chat_id_str, DEFAULT_GROUP_SETTINGS)
                    
                    if settings.get('auto_quote', True):
                        interval = settings.get('auto_quote_interval', 600)
                        await auto_messages.send_quote_if_needed(app.bot, chat_id, interval)
                    
                    if settings.get('auto_message', True):
                        interval = settings.get('auto_message_interval', 10800)
                        await auto_messages.send_auto_if_needed(app.bot, chat_id, interval)
                    
                    await asyncio.sleep(2)  # Small delay between groups
                    
                except Exception as e:
                    logger.error(f"Error processing group {chat_id_str}: {e}")
                    continue
            
            await asyncio.sleep(60)  # Check every minute
            
        except Exception as e:
            logger.error(f"Periodic task error: {e}")
            await asyncio.sleep(60)

# ==================== HEALTH CHECK ====================
async def health_check(request):
    """Simple health check"""
    return aiohttp.web.Response(
        text=json.dumps({
            "status": "ok",
            "timestamp": datetime.now().isoformat()
        }),
        status=200,
        content_type="application/json"
    )

async def run_web_server():
    """Run health check server"""
    try:
        from aiohttp import web
        
        app = web.Application()
        app.router.add_get('/', health_check)
        app.router.add_get('/health', health_check)
        app.router.add_get('/stats', health_stats)
        
        port = int(os.environ.get("PORT", 10000))
        
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', port)
        await site.start()
        
        logger.info(f"✅ Health check server running on port {port}")
        return runner
    except Exception as e:
        logger.error(f"Health server error: {e}")
        return None

async def health_stats(request):
    """Return basic stats"""
    stats = {
        "users": len(db.get('users', default={})),
        "groups": len(db.get('groups', default={})),
        "warnings": len(db.get('warnings', default={})),
        "uptime": time.time() - start_time if 'start_time' in globals() else 0
    }
    return aiohttp.web.json_response(stats)

# ==================== BROADCAST COMMAND ====================
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Broadcast message to all groups (admin only)"""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Admin only command!")
        return
    
    if not context.args:
        await update.message.reply_text("Usage: /broadcast [message]")
        return
    
    message = ' '.join(context.args)
    groups = db.get('groups', default={})
    
    status_msg = await update.message.reply_text(
        f"📢 Broadcasting to {len(groups)} groups..."
    )
    
    success = 0
    failed = 0
    
    for chat_id_str in groups:
        try:
            chat_id = int(chat_id_str)
            await context.bot.send_message(
                chat_id,
                f"📢 *Broadcast*\n\n{message}",
                parse_mode=ParseMode.MARKDOWN
            )
            success += 1
            await asyncio.sleep(0.5)  # Rate limiting
        except Exception as e:
            logger.error(f"Broadcast failed to {chat_id_str}: {e}")
            failed += 1
    
    await status_msg.edit_text(
        f"📢 *Broadcast Complete*\n\n✅ Success: {success}\n❌ Failed: {failed}",
        parse_mode=ParseMode.MARKDOWN
    )

# ==================== MAIN ====================
start_time = time.time()

async def main():
    """Main async function"""
    # Build application
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Add command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("rules", rules))
    app.add_handler(CommandHandler("mywarns", mywarns))
    app.add_handler(CommandHandler("warn", warn))
    app.add_handler(CommandHandler("broadcast", broadcast))
    
    # Add callback query handler
    app.add_handler(CallbackQueryHandler(button_callback))
    
    # Add message handlers
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_new))
    app.add_handler(MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER, goodbye_left))
    
    # Add error handler
    app.add_error_handler(error_handler)
    
    # Set bot commands
    try:
        await app.bot.set_my_commands([
            BotCommand("start", "Start the bot"),
            BotCommand("help", "Show help"),
            BotCommand("rules", "Show rules"),
            BotCommand("mywarns", "Check your warnings"),
            BotCommand("broadcast", "Broadcast to all groups (admin)")
        ])
    except Exception as e:
        logger.error(f"Failed to set commands: {e}")
    
    # Start health check server
    runner = await run_web_server()
    
    # Start periodic tasks
    asyncio.create_task(periodic_tasks(app))
    
    logger.info("🚀 Bot started! Fully automated")
    logger.info(f"Admin ID: {ADMIN_ID}")
    logger.info(f"Bot token: {BOT_TOKEN[:10]}...")
    
    # Start polling
    try:
        await app.run_polling(allowed_updates=Update.ALL_TYPES)
    finally:
        # Cleanup
        if runner:
            await runner.cleanup()

def run():
    """Entry point"""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    run()
