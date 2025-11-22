"""
Log Message Translator

Translates technical log messages into user-friendly, easy-to-understand messages.
"""

import re
from typing import Dict, Optional, Tuple
from enum import Enum


class MessageType(Enum):
    """Types of translated messages."""
    SUCCESS = "success"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    TRADE = "trade"
    THREAT = "threat"
    BOUNTY = "bounty"
    SYSTEM = "system"


class LogTranslator:
    """Translates technical log messages to user-friendly format."""

    def __init__(self):
        """Initialize the translator with pattern mappings."""
        # Pattern mappings: (regex_pattern, (translated_message, message_type, icon))
        self.patterns = [
            # Bot status
            (r"Starting Universal Trader", ("🚀 Bot is starting up...", MessageType.SYSTEM, "🚀")),
            (r"Bot started successfully", ("✅ Bot is now running!", MessageType.SUCCESS, "✅")),
            (r"Bot stopped", ("⏹️ Bot has stopped", MessageType.INFO, "⏹️")),
            (r"Bot paused", ("⏸️ Bot is paused", MessageType.WARNING, "⏸️")),
            (r"Bot resumed", ("▶️ Bot is running again", MessageType.SUCCESS, "▶️")),
            
            # Token detection
            (r"New token detected|Found token|Queued new token", ("🔍 New token detected!", MessageType.INFO, "🔍")),
            (r"Token.*symbol.*mint", self._extract_token_info),
            (r"Waiting for.*token", ("⏳ Waiting for new tokens...", MessageType.INFO, "⏳")),
            
            # Trading actions
            (r"Buying.*SOL worth", self._extract_buy_info),
            (r"Successfully bought", ("✅ Purchase successful!", MessageType.SUCCESS, "✅")),
            (r"Selling.*tokens", self._extract_sell_info),
            (r"Successfully sold", ("💰 Sale completed!", MessageType.SUCCESS, "💰")),
            (r"Transaction.*failed|Failed to.*buy|Failed to.*sell", ("❌ Transaction failed", MessageType.ERROR, "❌")),
            
            # Threat detection
            (r"Threat.*detected|Vulnerability.*found", ("⚠️ Security threat detected!", MessageType.THREAT, "⚠️")),
            (r"HONEYPOT DETECTED", ("🚨 HONEYPOT DETECTED - DO NOT TRADE!", MessageType.ERROR, "🚨")),
            (r"RUG PULL PREDICTED", ("🚨 RUG PULL PREDICTED - High risk!", MessageType.ERROR, "🚨")),
            (r"threat level.*critical|risk.*critical", ("🔴 Critical threat level!", MessageType.THREAT, "🔴")),
            (r"threat level.*high|risk.*high", ("🟠 High threat level", MessageType.THREAT, "🟠")),
            (r"threat level.*medium|risk.*medium", ("🟡 Medium threat level", MessageType.THREAT, "🟡")),
            (r"threat level.*low|risk.*low", ("🟢 Low threat level", MessageType.THREAT, "🟢")),
            
            # Bug bounty
            (r"Generating bug bounty report|Bug bounty report.*generated", ("📝 Generating bug bounty report...", MessageType.BOUNTY, "📝")),
            (r"Generated.*bug bounty report", self._extract_bounty_info),
            (r"Submission.*created|Created submission", ("📤 Bug bounty submission created", MessageType.BOUNTY, "📤")),
            (r"Payment.*detected|Bounty.*paid", ("💵 Bounty payment received!", MessageType.SUCCESS, "💵")),
            (r"Converting.*bounty.*liquidity", ("🔄 Converting bounty to liquidity...", MessageType.BOUNTY, "🔄")),
            (r"Liquidity.*created", self._extract_liquidity_info),
            
            # RPC/Connection
            (r"RPC.*warm-up.*successful|Connection.*established", ("🌐 Connected to Solana network", MessageType.SUCCESS, "🌐")),
            (r"RPC.*failed|Connection.*failed|Failed to connect", ("❌ Connection failed", MessageType.ERROR, "❌")),
            (r"Rate limit|Too many requests", ("⏱️ Rate limit reached - slowing down", MessageType.WARNING, "⏱️")),
            
            # Errors
            (r"Error|Exception|Traceback", ("❌ An error occurred", MessageType.ERROR, "❌")),
            (r"Warning|WARNING", ("⚠️ Warning", MessageType.WARNING, "⚠️")),
            
            # System messages
            (r"Initialized|Initialization.*complete", ("✅ Component initialized", MessageType.SUCCESS, "✅")),
            (r"Loading.*configuration", ("⚙️ Loading configuration...", MessageType.SYSTEM, "⚙️")),
            (r"Configuration.*loaded", ("✅ Configuration loaded", MessageType.SUCCESS, "✅")),
        ]

    def translate(self, message: str) -> Tuple[str, MessageType, str]:
        """Translate a log message to user-friendly format.
        
        Args:
            message: Original log message
            
        Returns:
            Tuple of (translated_message, message_type, icon)
        """
        message_lower = message.lower()
        
        # Check each pattern
        for pattern, handler in self.patterns:
            if isinstance(handler, tuple):
                # Direct translation
                if re.search(pattern, message, re.IGNORECASE):
                    return handler
            elif callable(handler):
                # Custom extraction function
                result = handler(message)
                if result:
                    return result
        
        # Default: return original message with info type
        return (message, MessageType.INFO, "ℹ️")

    def _extract_token_info(self, message: str) -> Optional[Tuple[str, MessageType, str]]:
        """Extract token information from message."""
        # Try to extract token symbol
        symbol_match = re.search(r"symbol[:\s]+(\w+)", message, re.IGNORECASE)
        mint_match = re.search(r"mint[:\s]+([A-Za-z0-9]+)", message, re.IGNORECASE)
        
        if symbol_match:
            symbol = symbol_match.group(1)
            return (f"🪙 Token: {symbol}", MessageType.INFO, "🪙")
        elif mint_match:
            mint = mint_match.group(1)[:8] + "..."
            return (f"🪙 Token detected: {mint}", MessageType.INFO, "🪙")
        
        return None

    def _extract_buy_info(self, message: str) -> Optional[Tuple[str, MessageType, str]]:
        """Extract buy information from message."""
        # Try to extract SOL amount
        sol_match = re.search(r"(\d+\.?\d*)\s*SOL", message, re.IGNORECASE)
        token_match = re.search(r"(\w+)", message)
        
        if sol_match:
            amount = sol_match.group(1)
            return (f"💵 Buying {amount} SOL worth of tokens...", MessageType.TRADE, "💵")
        
        return ("💵 Placing buy order...", MessageType.TRADE, "💵")

    def _extract_sell_info(self, message: str) -> Optional[Tuple[str, MessageType, str]]:
        """Extract sell information from message."""
        sol_match = re.search(r"(\d+\.?\d*)\s*SOL", message, re.IGNORECASE)
        
        if sol_match:
            amount = sol_match.group(1)
            return (f"💰 Selling for {amount} SOL...", MessageType.TRADE, "💰")
        
        return ("💰 Placing sell order...", MessageType.TRADE, "💰")

    def _extract_bounty_info(self, message: str) -> Optional[Tuple[str, MessageType, str]]:
        """Extract bug bounty information from message."""
        # Try to extract bounty amount
        bounty_match = re.search(r"\$?(\d+[,\d]*\.?\d*)", message)
        count_match = re.search(r"(\d+)\s*report", message, re.IGNORECASE)
        
        if bounty_match:
            amount = bounty_match.group(1)
            return (f"📝 Bug bounty report generated - Estimated: ${amount}", MessageType.BOUNTY, "📝")
        elif count_match:
            count = count_match.group(1)
            return (f"📝 Generated {count} bug bounty report(s)", MessageType.BOUNTY, "📝")
        
        return ("📝 Bug bounty report generated", MessageType.BOUNTY, "📝")

    def _extract_liquidity_info(self, message: str) -> Optional[Tuple[str, MessageType, str]]:
        """Extract liquidity information from message."""
        sol_match = re.search(r"(\d+\.?\d*)\s*SOL", message, re.IGNORECASE)
        
        if sol_match:
            amount = sol_match.group(1)
            return (f"💧 Created {amount} SOL in liquidity", MessageType.SUCCESS, "💧")
        
        return ("💧 Liquidity created successfully", MessageType.SUCCESS, "💧")

    def format_message(self, original: str, translated: str, msg_type: MessageType, icon: str) -> str:
        """Format a translated message for display.
        
        Args:
            original: Original log message
            translated: Translated message
            msg_type: Message type
            icon: Icon for the message
            
        Returns:
            Formatted message string
        """
        # Use translated message with icon
        return f"{icon} {translated}"

    def get_color_for_type(self, msg_type: MessageType) -> str:
        """Get color code for message type.
        
        Args:
            msg_type: Message type
            
        Returns:
            Color name for tkinter
        """
        color_map = {
            MessageType.SUCCESS: "green",
            MessageType.INFO: "blue",
            MessageType.WARNING: "orange",
            MessageType.ERROR: "red",
            MessageType.TRADE: "purple",
            MessageType.THREAT: "red",
            MessageType.BOUNTY: "darkblue",
            MessageType.SYSTEM: "gray",
        }
        return color_map.get(msg_type, "black")













