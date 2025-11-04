import numpy as np
from typing import List, Dict
from datetime import datetime, timedelta
from models import Asset, MarketScenario

class MarketModel:
    """
    Probabilistic market simulation using Monte Carlo methods.
    
    NOTE (Developer): This is a simplified market model designed for educational purposes.
    The apply_market_impact() function uses discrete price jumps rather than a true 
    systemic cascade or Agent-Based Model (ABM). For a production system or advanced 
    research, you would implement a more sophisticated model that accounts for:
    - Asset correlations and covariance matrices
    - Agent-based trading behaviors
    - Liquidity constraints
    - Order book dynamics
    
    This simplified model is appropriate for demonstrating basic concepts to students.
    """
    
    def __init__(self, base_volatility: float = 0.15):
        self.base_volatility = base_volatility
    
    def generate_price_series(
        self, 
        initial_price: float, 
        days: int, 
        scenario: MarketScenario
    ) -> List[float]:
        """
        Generate a price series using geometric Brownian motion
        with scenario-specific modifications
        """
        dt = 1 / 252  # Daily timestep (252 trading days per year)
        prices = [initial_price]
        
        # Scenario-specific parameters
        drift, volatility_multiplier = self._get_scenario_params(scenario, days)
        
        for _ in range(days - 1):
            # Random walk with drift
            random_shock = np.random.normal(0, 1)
            daily_return = drift * dt + volatility_multiplier * self.base_volatility * np.sqrt(dt) * random_shock
            new_price = prices[-1] * np.exp(daily_return)
            prices.append(max(new_price, 0.01))  # Prevent negative prices
        
        return prices
    
    def _get_scenario_params(self, scenario: MarketScenario, days: int) -> tuple:
        """Return (drift, volatility_multiplier) for each scenario"""
        if scenario == MarketScenario.CRASH:
            return (-0.3, 2.5)  # Strong negative drift, high volatility
        elif scenario == MarketScenario.BOOM:
            return (0.20, 1.2)  # Positive drift
        elif scenario == MarketScenario.BEAR:
            return (-0.10, 1.5)  # Moderate decline
        elif scenario == MarketScenario.SECTOR_BOOM:
            return (0.30, 1.8)  # Bubble-like growth
        elif scenario == MarketScenario.INTEREST_RATE_HIKE:
            return (-0.05, 1.3)  # Mild negative
        elif scenario == MarketScenario.PANIC_SELL:
            return (-0.25, 3.0)  # Extreme volatility
        else:
            return (0.08, 1.0)  # Normal market (long-term avg return ~8%)
    
    def apply_market_impact(self, prices: List[float], scenario: MarketScenario) -> List[float]:
        """
        Apply scenario-specific market events at certain points.
        
        NOTE (Developer): This is a simplified event model using discrete price jumps.
        A true systemic cascade would involve:
        - Correlated movements across assets
        - Feedback loops and momentum effects
        - Volume-based price adjustments
        - Agent-based panic behaviors
        
        For this educational tool, simple discrete jumps are sufficient to demonstrate
        market event concepts to students.
        """
        if scenario == MarketScenario.PANIC_SELL:
            # Sudden crash mid-simulation
            crash_day = len(prices) // 2
            for i in range(crash_day, len(prices)):
                if i < crash_day + 10:  # 10-day cascade
                    prices[i] *= (1 - 0.15)  # 15% daily drops
        elif scenario == MarketScenario.SECTOR_BOOM:
            # Exponential growth then correction
            peak = len(prices) * 0.7
            for i in range(int(peak), len(prices)):
                if prices[i] > prices[int(peak)] * 0.8:
                    prices[i] *= 0.95  # Gradual correction
        
        return prices

