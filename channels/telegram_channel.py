"""
Telegram Channel - Telegram bot integration
"""

import asyncio
from typing import Dict, Any, Optional
from datetime import datetime

from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

from channels.base_channel import Channel


class TelegramChannel(Channel):
    """
    Telegram bot integration channel.
    Provides messaging through Telegram bot API.
    """
    
    def __init__(self, channel_id: str = "telegram", config: Dict[str, Any] = None):
        """
        Initialize Telegram channel.
        
        Args:
            channel_id: Channel identifier
            config: Channel configuration (must include bot_token)
        """
        config = config or {}
        super().__init__(channel_id, config)
        
        # Telegram bot token
        self.bot_token = config.get("bot_token")
        if not self.bot_token:
            raise ValueError("Telegram bot_token is required in config")
        
        # Application and bot
        self.application: Optional[Application] = None
        self.bot: Optional[Bot] = None
        
        # Active chats: chat_id -> user_info
        self.active_chats: Dict[int, Dict[str, Any]] = {}
    
    async def start(self) -> bool:
        """Start the Telegram bot"""
        try:
            print(f"[TelegramChannel] Starting bot...")
            
            # Create application
            self.application = Application.builder().token(self.bot_token).build()
            self.bot = self.application.bot
            
            # Register handlers
            self.application.add_handler(CommandHandler("start", self.handle_start))
            self.application.add_handler(CommandHandler("help", self.handle_help))
            self.application.add_handler(CommandHandler("status", self.handle_status))
            self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text))
            
            # Start polling
            await self.application.initialize()
            await self.application.start()
            await self.application.updater.start_polling()
            
            self.is_connected = True
            
            # Get bot info
            bot_info = await self.bot.get_me()
            print(f"[TelegramChannel] Bot started: @{bot_info.username}")
            
            # Emit startup event
            self.emit_event(
                "WORKFLOW_STARTED",
                {"channel": "telegram", "bot_username": bot_info.username}
            )
            
            return True
            
        except Exception as e:
            print(f"[TelegramChannel] Failed to start: {e}")
            self.is_connected = False
            return False
    
    async def stop(self) -> bool:
        """Stop the Telegram bot"""
        try:
            print("[TelegramChannel] Stopping bot...")
            
            if self.application:
                await self.application.updater.stop()
                await self.application.stop()
                await self.application.shutdown()
            
            self.active_chats.clear()
            self.is_connected = False
            
            print("[TelegramChannel] Bot stopped")
            return True
            
        except Exception as e:
            print(f"[TelegramChannel] Error stopping: {e}")
            return False
    
    async def handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        chat_id = update.effective_chat.id
        user = update.effective_user
        
        # Store chat info
        self.active_chats[chat_id] = {
            "user_id": user.id,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name
        }
        
        welcome_message = (
            f"👋 Hello {user.first_name}!\n\n"
            "I'm AgentOS, your AI assistant. I can help you with:\n"
            "• Research and information retrieval\n"
            "• Code execution and programming\n"
            "• Web browsing and automation\n"
            "• System operations\n\n"
            "Just send me a message and I'll assist you!\n\n"
            "Commands:\n"
            "/help - Show this help message\n"
            "/status - Check bot status"
        )
        
        await update.message.reply_text(welcome_message)
        
        print(f"[TelegramChannel] New user: {user.username} ({chat_id})")
    
    async def handle_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        help_message = (
            "🤖 *AgentOS Help*\n\n"
            "*Available Commands:*\n"
            "/start - Start conversation\n"
            "/help - Show this help\n"
            "/status - Check bot status\n\n"
            "*How to use:*\n"
            "Simply send me any message and I'll respond using my AI capabilities.\n\n"
            "*Examples:*\n"
            "• \"What is the weather like?\"\n"
            "• \"Calculate 15 * 23\"\n"
            "• \"Search for Python tutorials\"\n"
            "• \"Open notepad\""
        )
        
        await update.message.reply_text(help_message, parse_mode="Markdown")
    
    async def handle_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command"""
        status = self.get_status()
        
        status_message = (
            f"📊 *Bot Status*\n\n"
            f"Connected: {'✅ Yes' if status['connected'] else '❌ No'}\n"
            f"Active chats: {len(self.active_chats)}\n"
            f"Message handlers: {status['handlers']}"
        )
        
        await update.message.reply_text(status_message, parse_mode="Markdown")
    
    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text messages"""
        chat_id = update.effective_chat.id
        user = update.effective_user
        text = update.message.text
        
        # Create message object
        message = {
            "from": str(chat_id),
            "user_id": user.id,
            "username": user.username,
            "content": text,
            "timestamp": datetime.now().isoformat(),
            "channel": "telegram"
        }
        
        # Notify handlers (will route to agent)
        await self._handle_incoming_message(message)
    
    async def send_message(self, to: str, message: str, **kwargs) -> bool:
        """
        Send message to Telegram chat.
        
        Args:
            to: Chat ID (as string)
            message: Message content
            **kwargs: Additional parameters (parse_mode, etc.)
            
        Returns:
            True if sent successfully
        """
        try:
            chat_id = int(to)
            parse_mode = kwargs.get("parse_mode", None)
            
            await self.bot.send_message(
                chat_id=chat_id,
                text=message,
                parse_mode=parse_mode
            )
            
            return True
            
        except Exception as e:
            print(f"[TelegramChannel] Error sending to {to}: {e}")
            return False
    
    async def send_typing_action(self, chat_id: int):
        """
        Send typing action to chat.
        
        Args:
            chat_id: Chat ID
        """
        try:
            await self.bot.send_chat_action(chat_id=chat_id, action="typing")
        except Exception as e:
            print(f"[TelegramChannel] Error sending typing action: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get channel status"""
        status = super().get_status()
        status.update({
            "active_chats": len(self.active_chats),
            "bot_token_set": bool(self.bot_token)
        })
        return status
