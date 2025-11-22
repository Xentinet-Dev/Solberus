"""
Telegram Scanner - Real-time Telegram channel monitoring for crypto signals.
"""

import asyncio
from datetime import datetime
from typing import List, Optional

from utils.logger import get_logger

logger = get_logger(__name__)

# Optional Telegram API integration
try:
    from telethon import TelegramClient
    from telethon.tl.types import Message
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    TelegramClient = None
    Message = None


class TelegramScanner:
    """Scanner for Telegram channels/groups related to crypto tokens."""
    
    def __init__(
        self,
        api_id: Optional[int] = None,
        api_hash: Optional[str] = None,
        phone: Optional[str] = None,
        session_string: Optional[str] = None,
    ):
        """Initialize Telegram scanner.
        
        Args:
            api_id: Telegram API ID (from https://my.telegram.org)
            api_hash: Telegram API hash
            phone: Phone number for authentication
            session_string: Pre-authenticated session string
        """
        self.api_id = api_id
        self.api_hash = api_hash
        self.phone = phone
        self.session_string = session_string
        
        self.client = None
        if TELEGRAM_AVAILABLE and api_id and api_hash:
            try:
                session_name = session_string or "telegram_scanner"
                self.client = TelegramClient(session_name, api_id, api_hash)
                logger.info("Telegram client initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Telegram client: {e}")
                self.client = None
    
    async def connect(self) -> bool:
        """Connect to Telegram.
        
        Returns:
            True if connected successfully
        """
        if not self.client:
            return False
        
        try:
            if not self.client.is_connected():
                await self.client.connect()
            
            if not await self.client.is_user_authorized():
                if self.phone:
                    await self.client.send_code_request(self.phone)
                    # Note: In production, you'd need to handle code input
                    logger.warning("Telegram requires phone code verification")
                    return False
            
            logger.info("Telegram connected successfully")
            return True
        except Exception as e:
            logger.exception(f"Error connecting to Telegram: {e}")
            return False
    
    async def get_messages(
        self,
        channel_username: str,
        limit: int = 100,
        search_query: Optional[str] = None,
    ) -> List[dict]:
        """Get messages from a Telegram channel.
        
        Args:
            channel_username: Channel username (e.g., "cryptosignals")
            limit: Maximum number of messages
            search_query: Optional search query
            
        Returns:
            List of message dictionaries
        """
        if not self.client or not await self.client.is_connected():
            if not await self.connect():
                return []
        
        try:
            messages = []
            async for message in self.client.iter_messages(
                channel_username,
                limit=limit,
                search=search_query,
            ):
                if message and message.text:
                    messages.append({
                        "id": message.id,
                        "text": message.text,
                        "date": message.date,
                        "views": message.views or 0,
                        "reactions": getattr(message, "reactions", None),
                        "author_id": message.from_id.user_id if message.from_id else None,
                    })
            
            logger.debug(f"Retrieved {len(messages)} messages from {channel_username}")
            return messages
            
        except Exception as e:
            logger.exception(f"Error getting Telegram messages: {e}")
            return []
    
    async def monitor_channel(
        self,
        channel_username: str,
        callback,
        keywords: Optional[List[str]] = None,
    ):
        """Monitor a Telegram channel for new messages.
        
        Args:
            channel_username: Channel to monitor
            callback: Async callback function(message_dict)
            keywords: Optional keywords to filter messages
        """
        if not self.client or not await self.client.is_connected():
            if not await self.connect():
                return
        
        @self.client.on(self.client.on_new_message)
        async def handler(event):
            if event.message and event.message.text:
                text = event.message.text.lower()
                
                # Filter by keywords if provided
                if keywords:
                    if not any(kw.lower() in text for kw in keywords):
                        return
                
                message_dict = {
                    "id": event.message.id,
                    "text": event.message.text,
                    "date": event.message.date,
                    "views": event.message.views or 0,
                    "channel": channel_username,
                }
                
                await callback(message_dict)
        
        logger.info(f"Monitoring Telegram channel: {channel_username}")
        await self.client.run_until_disconnected()

