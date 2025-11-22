"""
Reddit Scanner - Real-time Reddit monitoring for crypto signals.
"""

import asyncio
from datetime import datetime, timedelta
from typing import List, Optional

from utils.logger import get_logger

logger = get_logger(__name__)

# Optional Reddit API integration
try:
    import praw
    REDDIT_AVAILABLE = True
except ImportError:
    REDDIT_AVAILABLE = False
    praw = None


class RedditScanner:
    """Scanner for Reddit posts/comments related to crypto tokens."""
    
    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        user_agent: str = "TradingBot/1.0",
    ):
        """Initialize Reddit scanner.
        
        Args:
            client_id: Reddit API client ID
            client_secret: Reddit API client secret
            user_agent: User agent string (required by Reddit)
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.user_agent = user_agent
        
        self.reddit = None
        if REDDIT_AVAILABLE and client_id and client_secret:
            try:
                self.reddit = praw.Reddit(
                    client_id=client_id,
                    client_secret=client_secret,
                    user_agent=user_agent,
                )
                logger.info("Reddit API client initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Reddit client: {e}")
                self.reddit = None
    
    async def search_subreddit(
        self,
        subreddit_name: str,
        query: str,
        limit: int = 100,
        sort: str = "hot",  # "hot", "new", "top", "rising"
    ) -> List[dict]:
        """Search for posts in a subreddit.
        
        Args:
            subreddit_name: Subreddit name (e.g., "CryptoCurrency")
            query: Search query
            limit: Maximum number of results
            sort: Sort method
            
        Returns:
            List of post dictionaries
        """
        if not self.reddit:
            logger.debug("Reddit API not configured, skipping search")
            return []
        
        try:
            subreddit = self.reddit.subreddit(subreddit_name)
            posts = []
            
            # Search posts
            for post in subreddit.search(query, limit=limit, sort=sort):
                posts.append({
                    "id": post.id,
                    "title": post.title,
                    "selftext": post.selftext,
                    "url": post.url,
                    "score": post.score,
                    "upvote_ratio": post.upvote_ratio,
                    "num_comments": post.num_comments,
                    "created_utc": datetime.fromtimestamp(post.created_utc),
                    "author": str(post.author) if post.author else None,
                    "subreddit": subreddit_name,
                })
            
            logger.debug(f"Found {len(posts)} Reddit posts for query: {query}")
            return posts
            
        except Exception as e:
            logger.exception(f"Error searching Reddit: {e}")
            return []
    
    async def get_hot_posts(
        self,
        subreddit_name: str,
        limit: int = 100,
        time_filter: str = "day",  # "hour", "day", "week", "month", "year", "all"
    ) -> List[dict]:
        """Get hot posts from a subreddit.
        
        Args:
            subreddit_name: Subreddit name
            limit: Maximum number of posts
            time_filter: Time filter for "top" posts
            
        Returns:
            List of post dictionaries
        """
        if not self.reddit:
            return []
        
        try:
            subreddit = self.reddit.subreddit(subreddit_name)
            posts = []
            
            for post in subreddit.hot(limit=limit):
                posts.append({
                    "id": post.id,
                    "title": post.title,
                    "selftext": post.selftext,
                    "url": post.url,
                    "score": post.score,
                    "upvote_ratio": post.upvote_ratio,
                    "num_comments": post.num_comments,
                    "created_utc": datetime.fromtimestamp(post.created_utc),
                    "author": str(post.author) if post.author else None,
                    "subreddit": subreddit_name,
                })
            
            return posts
            
        except Exception as e:
            logger.exception(f"Error getting Reddit hot posts: {e}")
            return []
    
    def calculate_engagement_score(self, post: dict) -> float:
        """Calculate engagement score from Reddit post.
        
        Args:
            post: Post dictionary
            
        Returns:
            Engagement score (0.0 to 1.0)
        """
        score = post.get("score", 0)
        comments = post.get("num_comments", 0)
        upvote_ratio = post.get("upvote_ratio", 0.5)
        
        # Weighted engagement
        total_engagement = (
            score * upvote_ratio * 1.0 +
            comments * 2.0  # Comments indicate discussion
        )
        
        # Normalize (1000+ engagement = 1.0)
        engagement_score = min(total_engagement / 1000.0, 1.0)
        return engagement_score

