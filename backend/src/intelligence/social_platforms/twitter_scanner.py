"""
Twitter/X Scanner - Real-time Twitter monitoring for crypto signals.
"""

import asyncio
import re
from datetime import datetime, timedelta
from typing import List, Optional

from utils.logger import get_logger

logger = get_logger(__name__)

# Optional Twitter API integration
try:
    import tweepy
    TWITTER_AVAILABLE = True
except ImportError:
    TWITTER_AVAILABLE = False
    tweepy = None


class TwitterScanner:
    """Scanner for Twitter/X posts related to crypto tokens."""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        access_token: Optional[str] = None,
        access_token_secret: Optional[str] = None,
        bearer_token: Optional[str] = None,
    ):
        """Initialize Twitter scanner.
        
        Args:
            api_key: Twitter API key
            api_secret: Twitter API secret
            access_token: Twitter access token
            access_token_secret: Twitter access token secret
            bearer_token: Twitter Bearer token (for v2 API)
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.access_token = access_token
        self.access_token_secret = access_token_secret
        self.bearer_token = bearer_token
        
        self.client = None
        if TWITTER_AVAILABLE and bearer_token:
            try:
                self.client = tweepy.Client(
                    bearer_token=bearer_token,
                    consumer_key=api_key,
                    consumer_secret=api_secret,
                    access_token=access_token,
                    access_token_secret=access_token_secret,
                    wait_on_rate_limit=True,
                )
                logger.info("Twitter API client initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Twitter client: {e}")
                self.client = None
    
    async def search_tweets(
        self,
        query: str,
        max_results: int = 100,
        since_minutes: int = 60,
    ) -> List[dict]:
        """Search for tweets matching query.
        
        Args:
            query: Search query (e.g., "pump.fun OR solana token")
            max_results: Maximum number of results
            since_minutes: Only return tweets from last N minutes
            
        Returns:
            List of tweet dictionaries
        """
        if not self.client:
            logger.debug("Twitter API not configured, skipping search")
            return []
        
        try:
            # Calculate time range
            start_time = datetime.utcnow() - timedelta(minutes=since_minutes)
            
            # Search tweets
            tweets = []
            for tweet in tweepy.Paginator(
                self.client.search_recent_tweets,
                query=query,
                max_results=min(max_results, 100),  # API limit
                tweet_fields=["created_at", "public_metrics", "author_id"],
                start_time=start_time,
            ).flatten(limit=max_results):
                if tweet:
                    tweets.append({
                        "id": tweet.id,
                        "text": tweet.text,
                        "created_at": tweet.created_at,
                        "author_id": tweet.author_id,
                        "metrics": tweet.public_metrics if hasattr(tweet, "public_metrics") else {},
                    })
            
            logger.debug(f"Found {len(tweets)} tweets for query: {query}")
            return tweets
            
        except Exception as e:
            logger.exception(f"Error searching Twitter: {e}")
            return []
    
    def extract_token_mentions(self, text: str) -> List[str]:
        """Extract token symbols/addresses from tweet text.
        
        Args:
            text: Tweet text
            
        Returns:
            List of potential token mentions
        """
        mentions = []
        
        # Solana address pattern (base58, 32-44 chars)
        solana_address_pattern = r'\b[1-9A-HJ-NP-Za-km-z]{32,44}\b'
        addresses = re.findall(solana_address_pattern, text)
        mentions.extend(addresses)
        
        # Token symbol patterns (common formats)
        # $SYMBOL or #SYMBOL
        symbol_pattern = r'[$#]?([A-Z]{2,10})\b'
        symbols = re.findall(symbol_pattern, text)
        mentions.extend([s.upper() for s in symbols if len(s) >= 2])
        
        return list(set(mentions))  # Remove duplicates
    
    def calculate_engagement_score(self, metrics: dict) -> float:
        """Calculate engagement score from tweet metrics.
        
        Args:
            metrics: Tweet public metrics (likes, retweets, etc.)
            
        Returns:
            Engagement score (0.0 to 1.0)
        """
        if not metrics:
            return 0.0
        
        # Weighted engagement calculation
        likes = metrics.get("like_count", 0)
        retweets = metrics.get("retweet_count", 0)
        replies = metrics.get("reply_count", 0)
        quotes = metrics.get("quote_count", 0)
        
        # Normalize to 0-1 scale (using reasonable thresholds)
        total_engagement = (
            likes * 1.0 +
            retweets * 2.0 +  # Retweets are more valuable
            replies * 1.5 +
            quotes * 2.5  # Quote tweets are very valuable
        )
        
        # Normalize (1000+ engagement = 1.0)
        score = min(total_engagement / 1000.0, 1.0)
        return score

