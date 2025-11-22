"""
Social Media Scanner - Scans Twitter/X, Telegram, Discord for viral and mooning projects.
"""

import asyncio
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from utils.logger import get_logger

logger = get_logger(__name__)

# Optional AI integration
try:
    from ai.sentiment_analyzer import SentimentAnalyzer
    from ai.token_evaluator import TokenEvaluator
    AI_AVAILABLE = True
except ImportError:
    AI_AVAILABLE = False
    SentimentAnalyzer = None
    TokenEvaluator = None


@dataclass
class SocialSignal:
    """Social media signal for a token/project."""
    
    platform: str  # "twitter", "telegram", "discord"
    content: str
    author: str
    timestamp: datetime
    engagement_score: float  # 0.0 to 1.0 (likes, retweets, views)
    virality_score: float  # 0.0 to 1.0 (based on growth rate)
    token_mentions: List[str]  # Token symbols/addresses mentioned
    sentiment: str  # "positive", "neutral", "negative"
    is_mooning: bool  # Indicates if project is "mooning"
    url: Optional[str] = None


@dataclass
class ViralToken:
    """Viral token detected from social media."""
    
    token_symbol: str
    token_address: Optional[str]
    platform: str
    signals: List[SocialSignal]
    total_engagement: float
    virality_score: float
    first_seen: datetime
    last_seen: datetime
    mooning_indicators: List[str]


class SocialMediaScanner:
    """
    Scans social media platforms for viral and mooning projects.
    
    Supports:
    - Twitter/X scanning
    - Telegram channel monitoring
    - Discord server monitoring
    - Viral pattern detection
    - Mooning project identification
    """
    
    def __init__(
        self,
        enable_twitter: bool = True,
        enable_telegram: bool = True,
        enable_discord: bool = True,
        enable_reddit: bool = True,
        twitter_api_key: Optional[str] = None,
        twitter_bearer_token: Optional[str] = None,
        telegram_api_id: Optional[int] = None,
        telegram_api_hash: Optional[str] = None,
        discord_token: Optional[str] = None,
        reddit_client_id: Optional[str] = None,
        reddit_client_secret: Optional[str] = None,
        enable_ai: bool = True,
        openai_api_key: Optional[str] = None,
        llm_provider: str = "openai",
    ):
        """Initialize social media scanner.
        
        Args:
            enable_twitter: Enable Twitter/X scanning
            enable_telegram: Enable Telegram scanning
            enable_discord: Enable Discord scanning
            twitter_api_key: Twitter API key (optional, can use web scraping)
            telegram_api_id: Telegram API ID
            telegram_api_hash: Telegram API hash
            discord_token: Discord bot token
        """
        self.enable_twitter = enable_twitter
        self.enable_telegram = enable_telegram
        self.enable_discord = enable_discord
        self.enable_reddit = enable_reddit
        
        self.twitter_api_key = twitter_api_key or twitter_bearer_token
        self.twitter_bearer_token = twitter_bearer_token
        self.telegram_api_id = telegram_api_id
        self.telegram_api_hash = telegram_api_hash
        self.discord_token = discord_token
        self.reddit_client_id = reddit_client_id
        self.reddit_client_secret = reddit_client_secret
        
        self.detected_tokens: Dict[str, ViralToken] = {}
        self.recent_signals: List[SocialSignal] = []
        
        # Initialize AI components if available
        self.sentiment_analyzer = None
        self.token_evaluator = None
        
        if enable_ai and AI_AVAILABLE and SentimentAnalyzer:
            try:
                self.sentiment_analyzer = SentimentAnalyzer(
                    enable_llm=True,
                    llm_provider=llm_provider,
                    openai_api_key=openai_api_key,
                )
                self.token_evaluator = TokenEvaluator(
                    enable_llm=True,
                    llm_provider=llm_provider,
                    openai_api_key=openai_api_key,
                )
                logger.info("AI-powered sentiment analysis and token evaluation enabled")
            except Exception as e:
                logger.warning(f"Failed to initialize AI components: {e}")
                self.sentiment_analyzer = None
                self.token_evaluator = None
        
        # Mooning indicators
        self.mooning_keywords = [
            "moon", "🚀", "pump", "gem", "100x", "to the moon",
            "moonshot", "rocket", "bullish", "breakout", "surge",
            "explosive", "massive", "huge", "insane", "crazy gains"
        ]
        
        logger.info("Social Media Scanner initialized")
    
    async def scan_for_viral_tokens(
        self,
        keywords: Optional[List[str]] = None,
        platforms: Optional[List[str]] = None,
        max_results: int = 50,
    ) -> List[ViralToken]:
        """Scan social media for viral tokens.
        
        Args:
            keywords: Keywords to search for (default: common crypto terms)
            platforms: Platforms to scan (default: all enabled)
            max_results: Maximum number of results to return
            
        Returns:
            List of viral tokens detected
        """
        if keywords is None:
            keywords = ["pump", "moon", "gem", "token", "solana", "pumpfun"]
        
        if platforms is None:
            platforms = []
            if self.enable_twitter:
                platforms.append("twitter")
            if self.enable_telegram:
                platforms.append("telegram")
            if self.enable_discord:
                platforms.append("discord")
            if self.enable_reddit:
                platforms.append("reddit")
        
        logger.info(f"Scanning {', '.join(platforms)} for viral tokens...")
        
        all_signals: List[SocialSignal] = []
        
        # Scan each platform
        scan_tasks = []
        if "twitter" in platforms:
            scan_tasks.append(self._scan_twitter(keywords))
        if "telegram" in platforms:
            scan_tasks.append(self._scan_telegram(keywords))
        if "discord" in platforms:
            scan_tasks.append(self._scan_discord(keywords))
        
        if scan_tasks:
            results = await asyncio.gather(*scan_tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, list):
                    all_signals.extend(result)
                elif isinstance(result, Exception):
                    logger.exception(f"Error scanning platform: {result}")
        
        # Process signals to find viral tokens
        viral_tokens = self._process_signals_to_tokens(all_signals)
        
        # Sort by virality score
        viral_tokens.sort(key=lambda x: x.virality_score, reverse=True)
        
        # Update detected tokens
        for token in viral_tokens:
            if token.token_symbol not in self.detected_tokens:
                self.detected_tokens[token.token_symbol] = token
            else:
                # Update existing token
                existing = self.detected_tokens[token.token_symbol]
                existing.signals.extend(token.signals)
                existing.total_engagement += token.total_engagement
                existing.virality_score = max(existing.virality_score, token.virality_score)
                existing.last_seen = token.last_seen
        
        self.recent_signals = all_signals[:max_results]
        
        logger.info(f"Found {len(viral_tokens)} viral tokens")
        return viral_tokens[:max_results]
    
    async def _scan_twitter(self, keywords: List[str]) -> List[SocialSignal]:
        """Scan Twitter/X for viral tokens.
        
        Args:
            keywords: Keywords to search for
            
        Returns:
            List of social signals
        """
        signals: List[SocialSignal] = []
        
        try:
            # In production, this would:
            # 1. Use Twitter API or web scraping
            # 2. Search for keywords
            # 3. Analyze engagement metrics
            # 4. Extract token mentions
            # 5. Calculate virality scores
            
            logger.debug("Scanning Twitter/X...")
            
            # Placeholder - would use actual Twitter API
            # For now, simulate some results
            if self.twitter_api_key:
                # Would use tweepy or similar
                pass
            else:
                # Web scraping fallback (would use selenium/playwright)
                logger.debug("Twitter API not configured, using placeholder data")
            
            # Placeholder signals
            # In production, these would come from actual API calls
            
        except Exception as e:
            logger.exception(f"Error scanning Twitter: {e}")
        
        return signals
    
    async def _scan_telegram(self, keywords: List[str]) -> List[SocialSignal]:
        """Scan Telegram channels for viral tokens.
        
        Args:
            keywords: Keywords to search for
            
        Returns:
            List of social signals
        """
        signals: List[SocialSignal] = []
        
        try:
            logger.debug("Scanning Telegram...")
            
            # Try to use Telegram API if available
            try:
                from intelligence.social_platforms.telegram_scanner import TelegramScanner
                
                if not self.telegram_api_id or not self.telegram_api_hash:
                    logger.debug("Telegram API credentials not configured")
                    return signals
                
                telegram_scanner = TelegramScanner(
                    api_id=self.telegram_api_id,
                    api_hash=self.telegram_api_hash,
                )
                
                # Connect to Telegram
                if not await telegram_scanner.connect():
                    logger.warning("Failed to connect to Telegram")
                    return signals
                
                # Monitor popular crypto channels (configurable)
                crypto_channels = [
                    "cryptosignals",
                    "pumpfun",
                    "solana_tokens",
                ]
                
                for channel in crypto_channels:
                    try:
                        messages = await telegram_scanner.get_messages(
                            channel_username=channel,
                            limit=50,
                            search_query=" OR ".join(keywords) if keywords else None,
                        )
                        
                        for msg in messages:
                            # Extract token mentions (simplified)
                            content = msg.get("text", "")
                            token_mentions = self._extract_token_mentions_from_text(content)
                            
                            if not token_mentions:
                                continue
                            
                            # Calculate engagement (views as proxy)
                            views = msg.get("views", 0)
                            engagement_score = min(views / 1000.0, 1.0) if views else 0.0
                            
                            signal = SocialSignal(
                                platform="telegram",
                                content=content,
                                author=str(msg.get("author_id", "unknown")),
                                timestamp=msg.get("date", datetime.utcnow()),
                                engagement_score=engagement_score,
                                virality_score=0.0,
                                token_mentions=token_mentions,
                                sentiment="neutral",
                                is_mooning=False,
                            )
                            
                            # AI sentiment analysis
                            if self.sentiment_analyzer:
                                analysis = await self.sentiment_analyzer.analyze_sentiment(
                                    content=signal.content,
                                    source=f"telegram:{signal.author}",
                                )
                                signal.sentiment = analysis.overall_sentiment
                            
                            signals.append(signal)
                    except Exception as e:
                        logger.warning(f"Error scanning Telegram channel {channel}: {e}")
                        continue
                
                logger.info(f"Found {len(signals)} Telegram signals")
                
            except ImportError:
                logger.debug("Telegram API libraries not installed. Install with: pip install telethon")
            except Exception as e:
                logger.warning(f"Telegram API error: {e}")
            
        except Exception as e:
            logger.exception(f"Error scanning Telegram: {e}")
        
        return signals
    
    async def _scan_discord(self, keywords: List[str]) -> List[SocialSignal]:
        """Scan Discord servers for viral tokens.
        
        Args:
            keywords: Keywords to search for
            
        Returns:
            List of social signals
        """
        signals: List[SocialSignal] = []
        
        try:
            logger.debug("Scanning Discord...")
            
            # Try to use Discord API if available
            try:
                from intelligence.social_platforms.discord_scanner import DiscordScanner
                
                if not self.discord_token:
                    logger.debug("Discord bot token not configured")
                    return signals
                
                discord_scanner = DiscordScanner(bot_token=self.discord_token)
                
                # Note: Discord requires bot to be running and connected
                # For scanning, we'd need to configure channel IDs to monitor
                # This is a simplified version - full implementation would require
                # persistent bot connection and channel monitoring setup
                
                logger.debug("Discord scanning requires persistent bot connection (not implemented in scan mode)")
                
            except ImportError:
                logger.debug("Discord API libraries not installed. Install with: pip install discord.py")
            except Exception as e:
                logger.warning(f"Discord API error: {e}")
            
        except Exception as e:
            logger.exception(f"Error scanning Discord: {e}")
        
        return signals
    
    async def _scan_reddit(self, keywords: List[str]) -> List[SocialSignal]:
        """Scan Reddit for viral tokens.
        
        Args:
            keywords: Keywords to search for
            
        Returns:
            List of social signals
        """
        signals: List[SocialSignal] = []
        
        try:
            logger.debug("Scanning Reddit...")
            
            # Try to use Reddit API if available
            try:
                from intelligence.social_platforms.reddit_scanner import RedditScanner
                import os
                
                reddit_client_id = os.getenv("REDDIT_CLIENT_ID")
                reddit_client_secret = os.getenv("REDDIT_CLIENT_SECRET")
                
                if not reddit_client_id or not reddit_client_secret:
                    logger.debug("Reddit API credentials not configured")
                    return signals
                
                reddit_scanner = RedditScanner(
                    client_id=reddit_client_id,
                    client_secret=reddit_client_secret,
                )
                
                # Search popular crypto subreddits
                crypto_subreddits = [
                    "CryptoCurrency",
                    "solana",
                    "pumpfun",
                    "cryptomoon",
                ]
                
                query = " OR ".join(keywords) if keywords else "pump.fun OR solana token"
                
                for subreddit in crypto_subreddits:
                    try:
                        posts = await reddit_scanner.search_subreddit(
                            subreddit_name=subreddit,
                            query=query,
                            limit=25,
                            sort="hot",
                        )
                        
                        for post in posts:
                            # Extract token mentions
                            text = f"{post['title']} {post.get('selftext', '')}"
                            token_mentions = self._extract_token_mentions_from_text(text)
                            
                            if not token_mentions:
                                continue
                            
                            # Calculate engagement
                            engagement_score = reddit_scanner.calculate_engagement_score(post)
                            
                            signal = SocialSignal(
                                platform="reddit",
                                content=text[:500],  # Limit length
                                author=post.get("author", "unknown"),
                                timestamp=post.get("created_utc", datetime.utcnow()),
                                engagement_score=engagement_score,
                                virality_score=0.0,
                                token_mentions=token_mentions,
                                sentiment="neutral",
                                is_mooning=False,
                                url=post.get("url"),
                            )
                            
                            # AI sentiment analysis
                            if self.sentiment_analyzer:
                                analysis = await self.sentiment_analyzer.analyze_sentiment(
                                    content=signal.content,
                                    source=f"reddit:{signal.author}",
                                )
                                signal.sentiment = analysis.overall_sentiment
                            
                            signals.append(signal)
                    except Exception as e:
                        logger.warning(f"Error scanning Reddit subreddit {subreddit}: {e}")
                        continue
                
                logger.info(f"Found {len(signals)} Reddit signals")
                
            except ImportError:
                logger.debug("Reddit API libraries not installed. Install with: pip install praw")
            except Exception as e:
                logger.warning(f"Reddit API error: {e}")
            
        except Exception as e:
            logger.exception(f"Error scanning Reddit: {e}")
        
        return signals
    
    def _extract_token_mentions_from_text(self, text: str) -> List[str]:
        """Extract token symbols/addresses from text.
        
        Args:
            text: Text to analyze
            
        Returns:
            List of potential token mentions
        """
        import re
        mentions = []
        
        # Solana address pattern
        solana_address_pattern = r'\b[1-9A-HJ-NP-Za-km-z]{32,44}\b'
        addresses = re.findall(solana_address_pattern, text)
        mentions.extend(addresses)
        
        # Token symbol patterns
        symbol_pattern = r'[$#]?([A-Z]{2,10})\b'
        symbols = re.findall(symbol_pattern, text)
        mentions.extend([s.upper() for s in symbols if len(s) >= 2])
        
        return list(set(mentions))
    
    def _process_signals_to_tokens(self, signals: List[SocialSignal]) -> List[ViralToken]:
        """Process social signals to identify viral tokens.
        
        Args:
            signals: List of social signals
            
        Returns:
            List of viral tokens
        """
        token_map: Dict[str, List[SocialSignal]] = {}
        
        # Group signals by token
        for signal in signals:
            for token_symbol in signal.token_mentions:
                if token_symbol not in token_map:
                    token_map[token_symbol] = []
                token_map[token_symbol].append(signal)
        
        viral_tokens: List[ViralToken] = []
        
        for token_symbol, token_signals in token_map.items():
            if len(token_signals) < 2:  # Need at least 2 signals
                continue
            
            # Calculate metrics
            total_engagement = sum(s.engagement_score for s in token_signals)
            virality_score = self._calculate_virality_score(token_signals)
            
            # Check for mooning indicators
            mooning_indicators = self._detect_mooning_indicators(token_signals)
            is_mooning = len(mooning_indicators) > 0
            
            # Extract token address if mentioned
            token_address = self._extract_token_address(token_signals)
            
            # Use AI token evaluator if available
            ai_evaluation = None
            if self.token_evaluator and token_address:
                try:
                    # Get metadata and price data if available
                    metadata = {"symbol": token_symbol}
                    social_data = [{"platform": s.platform, "content": s.content} for s in token_signals]
                    
                    ai_evaluation = await self.token_evaluator.evaluate_token(
                        token_symbol=token_symbol,
                        token_address=token_address,
                        metadata=metadata,
                        social_signals=social_data,
                    )
                    
                    # Enhance mooning indicators with AI insights
                    if ai_evaluation.positive_indicators:
                        mooning_indicators.extend(ai_evaluation.positive_indicators)
                    if ai_evaluation.scam_indicators:
                        logger.warning(f"AI detected scam indicators for {token_symbol}: {ai_evaluation.scam_indicators}")
                except Exception as e:
                    logger.exception(f"Error in AI token evaluation: {e}")
            
            viral_token = ViralToken(
                token_symbol=token_symbol,
                token_address=token_address,
                platform=token_signals[0].platform,
                signals=token_signals,
                total_engagement=total_engagement,
                virality_score=virality_score,
                first_seen=min(s.timestamp for s in token_signals),
                last_seen=max(s.timestamp for s in token_signals),
                mooning_indicators=mooning_indicators,
                ai_evaluation=ai_evaluation,
            )
            
            viral_tokens.append(viral_token)
        
        return viral_tokens
    
    def _calculate_virality_score(self, signals: List[SocialSignal]) -> float:
        """Calculate virality score based on signals.
        
        Args:
            signals: List of social signals
            
        Returns:
            Virality score (0.0 to 1.0)
        """
        if not signals:
            return 0.0
        
        # Factors:
        # 1. Number of signals (more = more viral)
        # 2. Engagement scores
        # 3. Time concentration (signals close together = more viral)
        # 4. Platform diversity
        
        signal_count_score = min(len(signals) / 10.0, 1.0)  # Cap at 10 signals
        engagement_score = sum(s.engagement_score for s in signals) / len(signals)
        
        # Time concentration (signals within 1 hour = high virality)
        now = datetime.now()
        recent_signals = [s for s in signals if (now - s.timestamp).total_seconds() < 3600]
        time_score = len(recent_signals) / max(len(signals), 1)
        
        # Platform diversity
        platforms = set(s.platform for s in signals)
        diversity_score = len(platforms) / 3.0  # 3 platforms max
        
        virality = (
            signal_count_score * 0.3 +
            engagement_score * 0.3 +
            time_score * 0.2 +
            diversity_score * 0.2
        )
        
        return min(virality, 1.0)
    
    def _detect_mooning_indicators(self, signals: List[SocialSignal]) -> List[str]:
        """Detect mooning indicators in signals.
        
        Args:
            signals: List of social signals
            
        Returns:
            List of mooning indicators found
        """
        indicators = []
        
        for signal in signals:
            content_lower = signal.content.lower()
            
            # Check for mooning keywords
            for keyword in self.mooning_keywords:
                if keyword in content_lower:
                    indicators.append(f"'{keyword}' mentioned in {signal.platform}")
            
            # Check for price action mentions
            if re.search(r'\+\d+%|\d+x|pump|surge', content_lower):
                indicators.append(f"Price action mentioned in {signal.platform}")
            
            # High engagement + positive sentiment
            if signal.engagement_score > 0.7 and signal.sentiment == "positive":
                indicators.append(f"High engagement on {signal.platform}")
        
        return list(set(indicators))  # Remove duplicates
    
    def _extract_token_address(self, signals: List[SocialSignal]) -> Optional[str]:
        """Extract Solana token address from signals.
        
        Args:
            signals: List of social signals
            
        Returns:
            Token address if found, None otherwise
        """
        # Solana addresses are base58 encoded, typically 32-44 characters
        address_pattern = r'[1-9A-HJ-NP-Za-km-z]{32,44}'
        
        for signal in signals:
            matches = re.findall(address_pattern, signal.content)
            for match in matches:
                # Basic validation (would need more robust checking)
                if len(match) >= 32:
                    return match
        
        return None
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get scanner statistics.
        
        Returns:
            Statistics dictionary
        """
        return {
            "total_tokens_detected": len(self.detected_tokens),
            "total_signals": len(self.recent_signals),
            "mooning_tokens": sum(1 for t in self.detected_tokens.values() if t.mooning_indicators),
            "platforms_enabled": {
                "twitter": self.enable_twitter,
                "telegram": self.enable_telegram,
                "discord": self.enable_discord,
            },
        }

