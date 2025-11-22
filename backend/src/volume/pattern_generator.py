"""
Pattern Generator - Generate human-like trading patterns.

This module generates trading patterns that appear organic
and human-like rather than bot-generated.
"""

import random
import math
from typing import Literal


class PatternGenerator:
    """
    Generate organic-looking trading patterns.
    
    This class creates trading patterns that mimic human behavior,
    including varying trade sizes, timing, and buy/sell ratios.
    """
    
    def __init__(
        self,
        buy_sell_ratio: float = 0.6,  # 60% buys, 40% sells
        volatility_factor: float = 0.3,  # Trade size volatility
    ):
        """Initialize pattern generator.
        
        Args:
            buy_sell_ratio: Ratio of buys to sells (0.0 to 1.0)
            volatility_factor: Volatility in trade sizes (0.0 to 1.0)
        """
        self.buy_sell_ratio = buy_sell_ratio
        self.volatility_factor = volatility_factor
        
        self.trade_history: list[tuple[str, float]] = []  # (type, amount)
    
    def get_next_trade_type(
        self, current_volume: float, target_volume: float
    ) -> Literal["buy", "sell"]:
        """Get next trade type based on pattern.
        
        Args:
            current_volume: Current volume generated
            target_volume: Target volume
            
        Returns:
            "buy" or "sell"
        """
        # Early in volume generation, more buys
        # Later, more sells to balance
        progress = current_volume / target_volume if target_volume > 0 else 0.5
        
        # Adjust ratio based on progress
        # Start with more buys, end with more sells
        adjusted_ratio = self.buy_sell_ratio * (1 - progress * 0.3)
        
        # Add some randomness
        adjusted_ratio += random.uniform(-0.1, 0.1)
        adjusted_ratio = max(0.1, min(0.9, adjusted_ratio))
        
        return "buy" if random.random() < adjusted_ratio else "sell"
    
    def get_trade_size(self, min_size: float, max_size: float) -> float:
        """Get trade size using organic pattern.
        
        Args:
            min_size: Minimum trade size
            max_size: Maximum trade size
            
        Returns:
            Trade size in SOL
        """
        # Use log-normal distribution for more realistic sizes
        # Most trades are small, some are large
        
        mean = (min_size + max_size) / 2
        std_dev = (max_size - min_size) * self.volatility_factor
        
        # Generate log-normal value
        normal_value = random.gauss(0, 1)
        log_normal = math.exp(normal_value * std_dev + math.log(mean))
        
        # Clamp to range
        size = max(min_size, min(max_size, log_normal))
        
        return size
    
    def get_delay_seconds(self, min_delay: float, max_delay: float) -> float:
        """Get delay between trades using organic pattern.
        
        Args:
            min_delay: Minimum delay in seconds
            max_delay: Maximum delay in seconds
            
        Returns:
            Delay in seconds
        """
        # Use exponential distribution for delays
        # Most delays are short, some are long
        
        lambda_param = 1.0 / ((min_delay + max_delay) / 2)
        delay = random.expovariate(lambda_param)
        
        # Clamp to range
        delay = max(min_delay, min(max_delay, delay))
        
        return delay

