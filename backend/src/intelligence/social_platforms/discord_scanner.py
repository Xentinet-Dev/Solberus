"""
Discord Scanner - Real-time Discord server monitoring for crypto signals.
"""

import asyncio
from datetime import datetime
from typing import List, Optional

from utils.logger import get_logger

logger = get_logger(__name__)

# Optional Discord API integration
try:
    import discord
    from discord.ext import commands
    DISCORD_AVAILABLE = True
except ImportError:
    DISCORD_AVAILABLE = False
    discord = None
    commands = None


class DiscordScanner:
    """Scanner for Discord channels related to crypto tokens."""
    
    def __init__(
        self,
        bot_token: Optional[str] = None,
    ):
        """Initialize Discord scanner.
        
        Args:
            bot_token: Discord bot token
        """
        self.bot_token = bot_token
        self.bot = None
        self.monitored_channels = []
        
        if DISCORD_AVAILABLE and bot_token:
            try:
                intents = discord.Intents.default()
                intents.message_content = True
                intents.guilds = True
                
                self.bot = commands.Bot(command_prefix="!", intents=intents)
                logger.info("Discord bot initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Discord bot: {e}")
                self.bot = None
    
    async def start(self):
        """Start the Discord bot."""
        if not self.bot or not self.bot_token:
            logger.warning("Discord bot not configured")
            return
        
        try:
            await self.bot.start(self.bot_token)
        except Exception as e:
            logger.exception(f"Error starting Discord bot: {e}")
    
    async def get_messages(
        self,
        channel_id: int,
        limit: int = 100,
        search_query: Optional[str] = None,
    ) -> List[dict]:
        """Get messages from a Discord channel.
        
        Args:
            channel_id: Discord channel ID
            limit: Maximum number of messages
            search_query: Optional search query
            
        Returns:
            List of message dictionaries
        """
        if not self.bot or not self.bot.is_ready():
            logger.warning("Discord bot not ready")
            return []
        
        try:
            channel = self.bot.get_channel(channel_id)
            if not channel:
                logger.warning(f"Channel {channel_id} not found")
                return []
            
            messages = []
            async for message in channel.history(limit=limit):
                if search_query and search_query.lower() not in message.content.lower():
                    continue
                
                messages.append({
                    "id": message.id,
                    "content": message.content,
                    "author": str(message.author),
                    "created_at": message.created_at,
                    "reactions": [str(r.emoji) for r in message.reactions],
                    "channel_id": channel_id,
                })
            
            logger.debug(f"Retrieved {len(messages)} messages from channel {channel_id}")
            return messages
            
        except Exception as e:
            logger.exception(f"Error getting Discord messages: {e}")
            return []
    
    def setup_message_handler(self, callback, keywords: Optional[List[str]] = None):
        """Setup message handler for monitored channels.
        
        Args:
            callback: Async callback function(message_dict)
            keywords: Optional keywords to filter messages
        """
        if not self.bot:
            return
        
        @self.bot.event
        async def on_message(message):
            if message.author == self.bot.user:
                return
            
            # Filter by keywords if provided
            if keywords:
                content_lower = message.content.lower()
                if not any(kw.lower() in content_lower for kw in keywords):
                    return
            
            message_dict = {
                "id": message.id,
                "content": message.content,
                "author": str(message.author),
                "created_at": message.created_at,
                "channel_id": message.channel.id,
                "reactions": [str(r.emoji) for r in message.reactions],
            }
            
            await callback(message_dict)
        
        logger.info("Discord message handler configured")

