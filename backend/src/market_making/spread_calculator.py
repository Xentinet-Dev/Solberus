"""
Spread Calculator - Calculate optimal spread based on market volatility.

This module calculates dynamic spreads for market making based on:
- Base spread percentage
- Market volatility
- Price history
- Risk parameters
"""

import statistics
from typing import List, Optional

from utils.logger import get_logger

logger = get_logger(__name__)


class SpreadCalculator:
    """
    Calculate optimal spread for market making.
    
    Adjusts spread based on market volatility to maximize profit
    while maintaining competitive pricing.
    """
    
    def __init__(
        self,
        base_spread: float = 0.02,  # 2% base spread
        volatility_window: int = 10,  # Number of price points for volatility
        high_volatility_multiplier: float = 1.5,  # Increase spread in high volatility
        min_spread: float = 0.005,  # 0.5% minimum spread
        max_spread: float = 0.1,  # 10% maximum spread
    ):
        """Initialize spread calculator.
        
        Args:
            base_spread: Base spread percentage (0.02 = 2%)
            volatility_window: Number of price points for volatility calculation
            high_volatility_multiplier: Multiplier for high volatility periods
            min_spread: Minimum spread percentage
            max_spread: Maximum spread percentage
        """
        self.base_spread = base_spread
        self.volatility_window = volatility_window
        self.high_volatility_multiplier = high_volatility_multiplier
        self.min_spread = min_spread
        self.max_spread = max_spread
    
    def calculate_spread(self, price_history: List[float]) -> float:
        """Calculate spread based on price history.
        
        Args:
            price_history: List of recent prices (most recent last)
            
        Returns:
            Spread percentage (0.02 = 2%)
        """
        if len(price_history) < 2:
            return self.base_spread
        
        # Calculate volatility
        volatility = self._calculate_volatility(price_history)
        
        # Adjust spread based on volatility
        if volatility > 0.1:  # High volatility (>10%)
            spread = self.base_spread * self.high_volatility_multiplier
        elif volatility > 0.05:  # Medium volatility (5-10%)
            spread = self.base_spread * 1.25
        else:  # Low volatility (<5%)
            spread = self.base_spread
        
        # Clamp to min/max
        spread = max(self.min_spread, min(spread, self.max_spread))
        
        return spread
    
    def _calculate_volatility(self, price_history: List[float]) -> float:
        """Calculate price volatility.
        
        Args:
            price_history: List of prices
            
        Returns:
            Volatility as a percentage (0.1 = 10%)
        """
        if len(price_history) < 2:
            return 0.0
        
        # Use recent prices for volatility calculation
        recent_prices = price_history[-self.volatility_window:] if len(price_history) > self.volatility_window else price_history
        
        if len(recent_prices) < 2:
            return 0.0
        
        # Calculate returns (percentage changes)
        returns = []
        for i in range(1, len(recent_prices)):
            if recent_prices[i-1] > 0:
                ret = (recent_prices[i] - recent_prices[i-1]) / recent_prices[i-1]
                returns.append(abs(ret))
        
        if not returns:
            return 0.0
        
        # Calculate volatility as average absolute return
        volatility = statistics.mean(returns)
        
        return volatility
    
    def calculate_bid_price(self, current_price: float, spread: float) -> float:
        """Calculate bid price (buy price).
        
        Args:
            current_price: Current market price
            spread: Spread percentage
            
        Returns:
            Bid price (buy price)
        """
        return current_price * (1 - spread / 2)
    
    def calculate_ask_price(self, current_price: float, spread: float) -> float:
        """Calculate ask price (sell price).
        
        Args:
            current_price: Current market price
            spread: Spread percentage
            
        Returns:
            Ask price (sell price)
        """
        return current_price * (1 + spread / 2)

