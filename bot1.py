# Add this new class for scheduling
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
        DataManager.save_data("schedule.json", schedule_data)
    
    def load_schedule_data(self):
        """Load scheduling data from file"""
        data = DataManager.load_data("schedule.json", {})
        for chat_id, timestamp_str in data.items():
            try:
                self.last_message_time[chat_id] = datetime.fromisoformat(timestamp_str)
            except:
                pass

# Initialize scheduler
scheduler = ScheduledMessages()
scheduler.load_schedule_data()

# Enhanced AutoMessaging class with more message types
class EnhancedAutoMessaging(AutoMessaging):
    @staticmethod
    async def get_random_content():
        """Get random content from various categories"""
        content_types = [
            EnhancedAutoMessaging.get_greeting,
            EnhancedAutoMessaging.get_festival_wish,
            FreeAPIServices.get_quote,
            FreeAPIServices.get_song_suggestion,
            FreeAPIServices.get_joke,
            FreeAPIServices.get_advice,
            FreeAPIServices.get_fact,
            EnhancedAutoMessaging.get_motivation,
            EnhancedAutoMessaging.get_tip,
            EnhancedAutoMessaging.get_news_headline,
            EnhancedAutoMessaging.get_interesting_fact
        ]
        
        content_func = random.choice(content_types)
        return await content_func() if asyncio.iscoroutinefunction(content_func) else content_func()
    
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

# New periodic message sender
async def periodic_group_messages(context: ContextTypes.DEFAULT_TYPE):
    """Send periodic messages to all groups"""
    try:
        # Get all groups from your data
        groups = list(group_data.keys())
        
        # If no groups tracked, try to get from a separate file or use default
        if not groups:
            # Load groups from a separate file if you maintain one
            all_groups = DataManager.load_data("active_groups.json", [])
            groups = all_groups
        
        for group_id in groups:
            try:
                # Check if we should send a message to this group
                if scheduler.should_send_message(str(group_id), "every_3_hours"):
                    # Get random content
                    content = await EnhancedAutoMessaging.get_random_content()
                    
                    # Add some formatting
                    formatted_content = f"""
🤖 *Alita Assistant Update*

{content}

---
🕐 {datetime.now().strftime('%I:%M %p')} • Use /help for more features!
"""
                    # Send message
                    await context.bot.send_message(
                        chat_id=group_id,
                        text=formatted_content,
                        parse_mode='Markdown'
                    )
                    
                    # Update last message time
                    scheduler.update_last_message(str(group_id))
                    logger.info(f"✅ Periodic message sent to group {group_id}")
                    
                    # Small delay to avoid hitting rate limits
                    await asyncio.sleep(1)
                    
            except Exception as e:
                logger.error(f"❌ Failed to send to group {group_id}: {e}")
                continue
                
    except Exception as e:
        logger.error(f"❌ Periodic messaging error: {e}")

# Command to manually trigger auto-response in a group
async def trigger_auto_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command to manually trigger an auto-response (/auto or /autoresponse)"""
    # Check if in group
    if update.effective_chat.type not in ["group", "supergroup"]:
        await update.message.reply_text("❌ This command only works in groups!")
        return
    
    # Check if user has admin rights (optional)
    user = update.effective_user
    chat = update.effective_chat
    
    try:
        member = await chat.get_member(user.id)
        if member.status not in ['administrator', 'creator']:
            await update.message.reply_text("❌ Only admins can trigger auto-responses!")
            return
    except:
        pass  # Skip admin check if can't verify
    
    # Get random content
    content = await EnhancedAutoMessaging.get_random_content()
    
    formatted_content = f"""
🤖 *Auto Response Triggered*

{content}

---
Requested by: {user.first_name}
🕐 {datetime.now().strftime('%I:%M %p')}
"""
    
    await update.message.reply_text(formatted_content, parse_mode='Markdown')
    scheduler.update_last_message(str(chat.id))

# Command to set auto-response interval
async def set_auto_interval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set auto-response interval for the group (/setinterval [hours])"""
    if update.effective_chat.type not in ["group", "supergroup"]:
        await update.message.reply_text("❌ This command only works in groups!")
        return
    
    # Check admin rights
    user = update.effective_user
    chat = update.effective_chat
    
    try:
        member = await chat.get_member(user.id)
        if member.status not in ['administrator', 'creator']:
            await update.message.reply_text("❌ Only admins can set intervals!")
            return
    except:
        pass
    
    # Parse interval
    try:
        if context.args:
            hours = float(context.args[0])
            if hours < 1:
                await update.message.reply_text("❌ Interval must be at least 1 hour!")
                return
            
            # Save interval for this group
            intervals_file = "group_intervals.json"
            intervals = DataManager.load_data(intervals_file, {})
            intervals[str(chat.id)] = hours
            DataManager.save_data(intervals_file, intervals)
            
            await update.message.reply_text(
                f"✅ Auto-response interval set to {hours} hours!\n"
                f"The bot will now send updates every {hours} hours."
            )
        else:
            # Show current interval
            intervals = DataManager.load_data("group_intervals.json", {})
            current = intervals.get(str(chat.id), 3)
            await update.message.reply_text(
                f"📊 Current auto-response interval: {current} hours\n"
                f"To change: `/setinterval [hours]`\n"
                f"Example: `/setinterval 6` for 6 hours"
            )
    except ValueError:
        await update.message.reply_text("❌ Please provide a valid number of hours!")

# Command to toggle auto-responses
async def toggle_auto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Toggle auto-responses on/off for the group (/toggleauto)"""
    if update.effective_chat.type not in ["group", "supergroup"]:
        await update.message.reply_text("❌ This command only works in groups!")
        return
    
    # Check admin rights
    user = update.effective_user
    chat = update.effective_chat
    
    try:
        member = await chat.get_member(user.id)
        if member.status not in ['administrator', 'creator']:
            await update.message.reply_text("❌ Only admins can toggle auto-responses!")
            return
    except:
        pass
    
    # Toggle setting
    settings_file = "auto_settings.json"
    settings = DataManager.load_data(settings_file, {})
    chat_id = str(chat.id)
    
    current = settings.get(chat_id, True)
    settings[chat_id] = not current
    DataManager.save_data(settings_file, settings)
    
    status = "enabled" if settings[chat_id] else "disabled"
    await update.message.reply_text(f"✅ Auto-responses {status} for this group!")

# Function to start the periodic task manually (without JobQueue)
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
                # The actual interval is controlled by scheduler.should_send_message
                await asyncio.sleep(3600)  # Check every hour
                
            except Exception as e:
                logger.error(f"Periodic wrapper error: {e}")
                await asyncio.sleep(60)  # Wait 1 minute on error
    
    # Create and start the task
    asyncio.create_task(periodic_wrapper())

# Add these to your main() function
def main():
    # ... your existing code ...
    
    # Create application
    application = Application.builder().token(TOKEN).build()
    
    # Add new command handlers
    application.add_handler(CommandHandler("auto", trigger_auto_response))
    application.add_handler(CommandHandler("autoresponse", trigger_auto_response))
    application.add_handler(CommandHandler("setinterval", set_auto_interval))
    application.add_handler(CommandHandler("toggleauto", toggle_auto))
    
    # ... rest of your handlers ...
    
    # Start periodic messages after bot starts
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
        
        # Start periodic messages
        await start_periodic_messages(application)
        logger.info("✅ Periodic messaging started")
    
    application.post_init = post_init
    
    # ... rest of your main function ...
