from sqlmodel import SQLModel, Field, Relationship
from typing import List, Optional, Dict, Literal, TYPE_CHECKING
from datetime import datetime
from enum import Enum

# Forward references for relationships
if TYPE_CHECKING:
    from typing import List

class AssetType(str, Enum):
    STOCK = "stock"
    BOND = "bond"
    ETF = "etf"

class Asset(SQLModel, table=True):
    """Asset model stored in database"""
    symbol: str = Field(primary_key=True)
    name: str
    asset_type: str  # Store as string for simplicity in database
    sector: Optional[str] = Field(default=None, index=True)
    current_price: float = Field(gt=0)
    
    # Relationship to positions
    positions: List["PortfolioPosition"] = Relationship(back_populates="asset")

class PortfolioPosition(SQLModel, table=True):
    """Portfolio position model stored in database"""
    id: Optional[int] = Field(default=None, primary_key=True)
    quantity: float = Field(ge=0)
    average_cost: float = Field(gt=0)
    
    # Foreign keys
    asset_symbol: str = Field(foreign_key="asset.symbol")
    portfolio_id: str = Field(foreign_key="portfolio.id")
    
    # Relationships
    asset: Asset = Relationship(back_populates="positions")
    portfolio: "Portfolio" = Relationship(back_populates="positions")

class Portfolio(SQLModel, table=True):
    """Portfolio model stored in database"""
    id: str = Field(primary_key=True)
    name: str
    cash: float = Field(ge=0, default=100000.0)
    created_at: datetime = Field(default_factory=datetime.now)
    
    # Relationship to positions
    positions: List[PortfolioPosition] = Relationship(back_populates="portfolio")
    
    def total_value(self, session=None) -> float:
        """
        Calculate total portfolio value.
        Note: In database-backed version, positions are loaded via relationship.
        """
        positions_value = sum(
            pos.asset.current_price * pos.quantity 
            for pos in self.positions
        )
        return self.cash + positions_value

# Pydantic models for request/response (not stored in database)
from pydantic import BaseModel

class TradeRequest(BaseModel):
    portfolio_id: str
    symbol: str
    quantity: float = Field(gt=0)
    action: Literal["buy", "sell"]

class MarketScenario(str, Enum):
    CRASH = "crash"  # Market crash (e.g., 2008)
    BOOM = "boom"  # Bull market
    BEAR = "bear"  # Bear market
    SECTOR_BOOM = "sector_boom"  # Tech bubble, etc.
    INTEREST_RATE_HIKE = "interest_rate_hike"
    PANIC_SELL = "panic_sell"

class SimulationRequest(BaseModel):
    portfolio_id: str
    scenario: MarketScenario
    duration_days: int = Field(default=252, ge=1, le=2520)  # Max 10 years

class SimulationResult(BaseModel):
    portfolio_id: str
    scenario: MarketScenario
    initial_value: float
    final_value: float
    peak_value: float
    drawdown: float  # Maximum loss from peak
    daily_returns: List[float]
    daily_values: List[float]
    risk_metrics: Dict[str, float]  # Sharpe ratio, volatility, etc.

class PortfolioAnalysis(BaseModel):
    portfolio_id: str
    total_value: float
    cash: float
    invested_value: float
    diversification_score: float = Field(ge=0, le=1)  # 0 = concentrated, 1 = diversified
    sector_exposure: Dict[str, float]  # Percentage per sector
    risk_level: Literal["low", "medium", "high"]
    sharpe_ratio: Optional[float] = None
    volatility: float

class ComparePortfoliosRequest(BaseModel):
    portfolio_1_id: str
    portfolio_2_id: str
    scenario: MarketScenario
    duration_days: int = 252

class ComparisonResult(BaseModel):
    portfolio_1_result: SimulationResult
    portfolio_2_result: SimulationResult
    winner: str  # Portfolio ID with better performance
    difference_percentage: float

