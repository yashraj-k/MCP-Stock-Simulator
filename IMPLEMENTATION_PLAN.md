# AI-Assisted Financial Tutor: Implementation Plan

## Overview

This document provides a detailed, phase-by-phase implementation plan for building the AI-Assisted Financial Tutor system, integrating FastAPI (simulation engine), FastMCP (AI bridge), and educational evaluation components.

## Key Architecture Decisions

### Database Persistence (Critical)
This implementation uses **SQLite + SQLModel** for persistent data storage instead of in-memory dictionaries. This ensures:
- Portfolios persist across server restarts
- User study data is preserved
- Multiple users can work with their own portfolios
- Production-ready data management

The database file (`simulator.db`) is created automatically on first run.

### Developer Notes
This plan includes developer notes acknowledging simplifications in:
- **Market Model**: Uses discrete price jumps rather than true systemic cascades (appropriate for education)
- **Volatility Calculation**: Hardcoded volatility instead of covariance matrix calculation (acceptable for prototype)

These simplifications are clearly documented and acceptable for an educational tool.

---

## Phase 1: FastAPI Simulation Engine

### Objective
Build a robust, API-driven stock market simulator with probabilistic modeling, event systems, and portfolio management capabilities.

### Prerequisites
- Python 3.9+ installed
- `pip` or `poetry` for dependency management
- Basic understanding of FastAPI, Pydantic, and async Python

### Step 1.1: Project Structure Setup

Create the following directory structure:

```
project_root/
├── simulation_engine/
│   ├── __init__.py
│   ├── main.py              # FastAPI application
│   ├── models.py            # Pydantic models
│   ├── simulation_logic.py  # Core simulation algorithms
│   ├── portfolio_manager.py # Portfolio operations
│   ├── market_model.py      # Market dynamics engine
│   └── events.py            # Market event/scenario handlers
├── requirements.txt
├── .env.example
└── README.md
```

**Commands:**
```bash
mkdir -p simulation_engine
cd simulation_engine
touch __init__.py main.py models.py simulation_logic.py portfolio_manager.py market_model.py events.py
cd ..
touch requirements.txt .env.example README.md
```

### Step 1.2: Environment Setup

**1.2.1 Create Virtual Environment:**
```bash
python -m venv venv
source venv/bin/activate  # On macOS/Linux
# OR
venv\Scripts\activate  # On Windows
```

**1.2.2 Install Dependencies (`requirements.txt`):**
```txt
fastapi==0.104.1
uvicorn[standard]==0.24.0
pydantic==2.5.0
pydantic-settings==2.1.0
sqlmodel==0.0.11
numpy==1.24.3
pandas==2.1.3
httpx==0.25.1
python-dotenv==1.0.0
```

**1.2.3 Create `.env.example`:**
```env
# Server Configuration
API_HOST=0.0.0.0
API_PORT=8000
API_URL=http://localhost:8000

# Simulation Configuration
DEFAULT_INITIAL_CASH=100000
DEFAULT_SIMULATION_DAYS=252  # 1 trading year
MARKET_VOLATILITY=0.15  # Default annual volatility
```

**1.2.4 Install:**
```bash
pip install -r requirements.txt
```

### Step 1.3: Define SQLModel Models (`models.py`)

Create comprehensive data models using SQLModel (which provides both Pydantic validation and SQLAlchemy ORM capabilities):

```python
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
```

### Step 1.4: Implement Market Model (`market_model.py`)

Create the probabilistic market dynamics engine:

```python
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
```

### Step 1.5: Implement Portfolio Manager (`portfolio_manager.py`)

Handle portfolio operations using database sessions:

```python
from typing import Dict, List, Optional
from sqlmodel import Session, select
from models import Portfolio, PortfolioPosition, Asset, TradeRequest
from collections import defaultdict

class PortfolioManager:
    """
    Manages portfolio state and operations.
    Now uses database sessions instead of in-memory storage.
    """
    
    def create_portfolio(self, session: Session, portfolio_id: str, name: str, initial_cash: float = 100000.0) -> Portfolio:
        """Create a new portfolio in the database"""
        portfolio = Portfolio(
            id=portfolio_id,
            name=name,
            cash=initial_cash,
            positions=[]
        )
        session.add(portfolio)
        session.commit()
        session.refresh(portfolio)
        return portfolio
    
    def get_portfolio(self, session: Session, portfolio_id: str) -> Optional[Portfolio]:
        """Retrieve portfolio by ID from database"""
        return session.get(Portfolio, portfolio_id)
    
    def execute_trade(self, session: Session, trade: TradeRequest, asset: Asset) -> Portfolio:
        """Execute a buy or sell order"""
        portfolio = self.get_portfolio(session, trade.portfolio_id)
        if not portfolio:
            raise ValueError(f"Portfolio {trade.portfolio_id} not found")
        
        # Refresh positions from database
        session.refresh(portfolio)
        
        if trade.action == "buy":
            cost = asset.current_price * trade.quantity
            if portfolio.cash < cost:
                raise ValueError("Insufficient cash")
            
            # Find existing position
            existing_pos = next(
                (p for p in portfolio.positions if p.asset_symbol == trade.symbol),
                None
            )
            
            if existing_pos:
                # Update existing position
                total_cost = (existing_pos.average_cost * existing_pos.quantity) + cost
                existing_pos.quantity += trade.quantity
                existing_pos.average_cost = total_cost / existing_pos.quantity
            else:
                # Create new position
                new_position = PortfolioPosition(
                    asset_symbol=trade.symbol,
                    portfolio_id=trade.portfolio_id,
                    quantity=trade.quantity,
                    average_cost=asset.current_price
                )
                session.add(new_position)
                portfolio.positions.append(new_position)
            
            portfolio.cash -= cost
        
        elif trade.action == "sell":
            # Find position
            position = next(
                (p for p in portfolio.positions if p.asset_symbol == trade.symbol),
                None
            )
            
            if not position or position.quantity < trade.quantity:
                raise ValueError("Insufficient shares")
            
            proceeds = asset.current_price * trade.quantity
            position.quantity -= trade.quantity
            portfolio.cash += proceeds
            
            # Remove position if quantity is zero
            if position.quantity == 0:
                session.delete(position)
                portfolio.positions.remove(position)
        
        session.add(portfolio)
        session.commit()
        session.refresh(portfolio)
        return portfolio
    
    def calculate_diversification_score(self, portfolio: Portfolio) -> float:
        """Calculate diversification score (0-1, where 1 is fully diversified)"""
        if not portfolio.positions:
            return 0.0
        
        # Get position values (positions loaded via relationship)
        total_value = portfolio.total_value()
        if total_value == 0:
            return 0.0
        
        position_weights = [
            (pos.asset.current_price * pos.quantity) / total_value
            for pos in portfolio.positions
        ]
        
        # Calculate Herfindahl-Hirschman Index (HHI)
        # Lower HHI = more diversified
        hhi = sum(w**2 for w in position_weights)
        
        # Convert to diversification score (0-1)
        max_hhi = 1.0  # All in one asset
        min_hhi = 1.0 / len(position_weights) if position_weights else 1.0
        
        if max_hhi == min_hhi:
            return 0.0
        
        diversification = 1 - ((hhi - min_hhi) / (max_hhi - min_hhi))
        return max(0.0, min(1.0, diversification))
    
    def calculate_sector_exposure(self, portfolio: Portfolio) -> Dict[str, float]:
        """Calculate percentage exposure by sector"""
        total_value = portfolio.total_value()
        if total_value == 0:
            return {}
        
        sector_values = defaultdict(float)
        for pos in portfolio.positions:
            # Access asset via relationship (loaded from database)
            sector = pos.asset.sector or "Unknown"
            value = pos.asset.current_price * pos.quantity
            sector_values[sector] += value
        
        return {
            sector: (value / total_value) * 100
            for sector, value in sector_values.items()
        }
```

### Step 1.6: Implement Simulation Logic (`simulation_logic.py`)

Core simulation algorithms:

```python
import numpy as np
from typing import List
from sqlmodel import Session
from models import Portfolio, SimulationRequest, SimulationResult, MarketScenario, Asset
from market_model import MarketModel
from portfolio_manager import PortfolioManager

class SimulationEngine:
    """Runs market simulations on portfolios"""
    
    def __init__(self, portfolio_manager: PortfolioManager):
        self.portfolio_manager = portfolio_manager
        self.market_model = MarketModel()
    
    def run_simulation(self, session: Session, request: SimulationRequest) -> SimulationResult:
        """Run a market scenario simulation"""
        portfolio = self.portfolio_manager.get_portfolio(session, request.portfolio_id)
        if not portfolio:
            raise ValueError(f"Portfolio {request.portfolio_id} not found")
        
        # Ensure positions and their assets are loaded
        session.refresh(portfolio)
        # Load assets for all positions
        for pos in portfolio.positions:
            if not pos.asset:
                pos.asset = session.get(Asset, pos.asset_symbol)
        
        initial_value = portfolio.total_value()
        initial_prices = {
            pos.asset_symbol: pos.asset.current_price
            for pos in portfolio.positions
        }
        
        # Generate price series for each asset
        price_series = {}
        for symbol, initial_price in initial_prices.items():
            prices = self.market_model.generate_price_series(
                initial_price,
                request.duration_days,
                request.scenario
            )
            price_series[symbol] = self.market_model.apply_market_impact(
                prices, request.scenario
            )
        
        # Calculate portfolio value over time
        daily_values = []
        daily_returns = []
        peak_value = initial_value
        
        for day in range(request.duration_days):
            # Calculate current portfolio value
            current_value = portfolio.cash
            for pos in portfolio.positions:
                symbol = pos.asset_symbol
                current_price = price_series[symbol][day]
                current_value += current_price * pos.quantity
            
            daily_values.append(current_value)
            
            # Calculate daily return
            if day > 0:
                daily_return = (current_value - daily_values[day - 1]) / daily_values[day - 1]
                daily_returns.append(daily_return)
            
            # Track peak
            if current_value > peak_value:
                peak_value = current_value
        
        final_value = daily_values[-1]
        drawdown = (peak_value - final_value) / peak_value if peak_value > 0 else 0
        
        # Calculate risk metrics
        if len(daily_returns) > 0:
            volatility = np.std(daily_returns) * np.sqrt(252)  # Annualized
            avg_return = np.mean(daily_returns) * 252  # Annualized
            sharpe_ratio = (avg_return - 0.03) / volatility if volatility > 0 else 0  # Risk-free rate = 3%
        else:
            volatility = 0
            sharpe_ratio = 0
        
        return SimulationResult(
            portfolio_id=request.portfolio_id,
            scenario=request.scenario,
            initial_value=initial_value,
            final_value=final_value,
            peak_value=peak_value,
            drawdown=drawdown,
            daily_returns=daily_returns,
            daily_values=daily_values,
            risk_metrics={
                "sharpe_ratio": sharpe_ratio,
                "volatility": volatility,
                "total_return": (final_value - initial_value) / initial_value,
                "max_drawdown": drawdown
            }
        )
    
    def analyze_portfolio(self, session: Session, portfolio_id: str) -> Dict:
        """Analyze portfolio risk and diversification"""
        portfolio = self.portfolio_manager.get_portfolio(session, portfolio_id)
        if not portfolio:
            raise ValueError(f"Portfolio {portfolio_id} not found")
        
        # Ensure positions are loaded
        session.refresh(portfolio)
        
        # Calculate metrics
        total_value = portfolio.total_value()
        diversification_score = self.portfolio_manager.calculate_diversification_score(portfolio)
        sector_exposure = self.portfolio_manager.calculate_sector_exposure(portfolio)
        
        # Determine risk level
        if diversification_score > 0.7 and len(portfolio.positions) >= 5:
            risk_level = "low"
        elif diversification_score > 0.4:
            risk_level = "medium"
        else:
            risk_level = "high"
        
        # NOTE (Developer): Volatility is hardcoded here as a simplification.
        # In a production system, portfolio volatility should be calculated using:
        # - Historical returns for each asset in the portfolio
        # - Asset correlations and covariance matrix
        # - Portfolio weights
        # Formula: σ_portfolio = sqrt(w^T * Σ * w)
        # where w is the weight vector and Σ is the covariance matrix.
        # For this educational tool, a fixed volatility is acceptable.
        volatility = 0.15  # Default, simplified for educational purposes
        
        return {
            "portfolio_id": portfolio_id,
            "total_value": total_value,
            "cash": portfolio.cash,
            "invested_value": total_value - portfolio.cash,
            "diversification_score": diversification_score,
            "sector_exposure": sector_exposure,
            "risk_level": risk_level,
            "volatility": volatility,
            "sharpe_ratio": None  # Would need returns history
        }
```

### Step 1.7: Create FastAPI Application (`main.py`)

Implement all API endpoints with database integration:

```python
from fastapi import FastAPI, HTTPException, status, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import SQLModel, create_engine, Session, select
from typing import List
import uvicorn
import uuid
from models import (
    Portfolio, TradeRequest, SimulationRequest, SimulationResult,
    PortfolioAnalysis, ComparePortfoliosRequest, ComparisonResult, Asset
)
from portfolio_manager import PortfolioManager
from simulation_logic import SimulationEngine

app = FastAPI(
    title="AI-Assisted Financial Tutor - Simulation Engine",
    description="API-driven stock market simulator",
    version="1.0.0"
)

# CORS middleware (for MCP server to call this API)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database Setup
DATABASE_FILE = "simulator.db"
sqlite_url = f"sqlite:///{DATABASE_FILE}"
engine = create_engine(sqlite_url, echo=True)  # echo=True shows SQL commands in logs

def create_db_and_tables():
    """Create database tables on startup"""
    SQLModel.metadata.create_all(engine)

def get_session():
    """Dependency to get database session"""
    with Session(engine) as session:
        yield session

# Initialize managers (no longer need to store portfolios in memory)
portfolio_manager = PortfolioManager()
simulation_engine = SimulationEngine(portfolio_manager)

# Sample assets to pre-populate (stored in database)
SAMPLE_ASSETS_DATA = [
    {"symbol": "AAPL", "name": "Apple Inc.", "asset_type": "stock", "sector": "Technology", "current_price": 150.0},
    {"symbol": "GOOGL", "name": "Alphabet Inc.", "asset_type": "stock", "sector": "Technology", "current_price": 140.0},
    {"symbol": "MSFT", "name": "Microsoft Corp.", "asset_type": "stock", "sector": "Technology", "current_price": 380.0},
    {"symbol": "JPM", "name": "JPMorgan Chase", "asset_type": "stock", "sector": "Finance", "current_price": 150.0},
    {"symbol": "VTI", "name": "Vanguard Total Stock Market ETF", "asset_type": "etf", "sector": "Diversified", "current_price": 230.0},
]

def populate_assets(session: Session):
    """Pre-populate assets in database if they don't exist"""
    for asset_data in SAMPLE_ASSETS_DATA:
        existing = session.get(Asset, asset_data["symbol"])
        if not existing:
            asset = Asset(**asset_data)
            session.add(asset)
    session.commit()

@app.on_event("startup")
def on_startup():
    """Initialize database and populate sample assets on startup"""
    create_db_and_tables()
    with Session(engine) as session:
        populate_assets(session)

@app.get("/")
def root():
    return {"message": "Financial Simulation Engine API", "version": "1.0.0"}

@app.post("/portfolios", response_model=Portfolio, status_code=status.HTTP_201_CREATED)
def create_portfolio(
    name: str,
    initial_cash: float = 100000.0,
    session: Session = Depends(get_session)
):
    """Create a new portfolio"""
    portfolio_id = f"portfolio_{uuid.uuid4()}"  # Use UUID for unique IDs
    portfolio = portfolio_manager.create_portfolio(session, portfolio_id, name, initial_cash)
    return portfolio

@app.get("/portfolios/{portfolio_id}", response_model=Portfolio)
def get_portfolio(
    portfolio_id: str,
    session: Session = Depends(get_session)
):
    """Get portfolio by ID"""
    portfolio = portfolio_manager.get_portfolio(session, portfolio_id)
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    return portfolio

@app.get("/portfolios", response_model=List[Portfolio])
def list_portfolios(session: Session = Depends(get_session)):
    """List all portfolios"""
    statement = select(Portfolio)
    portfolios = session.exec(statement).all()
    return list(portfolios)

@app.post("/trades")
def execute_trade(trade: TradeRequest, session: Session = Depends(get_session)):
    """
    Execute a trade (buy/sell).
    Note: Endpoint simplified from POST /portfolios/{portfolio_id}/trades
    since portfolio_id is already in TradeRequest body.
    """
    portfolio = portfolio_manager.get_portfolio(session, trade.portfolio_id)
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    
    asset = session.get(Asset, trade.symbol.upper())
    if not asset:
        raise HTTPException(status_code=404, detail=f"Asset {trade.symbol} not found")
    
    try:
        updated_portfolio = portfolio_manager.execute_trade(session, trade, asset)
        return {
            "message": f"Trade executed: {trade.action} {trade.quantity} {trade.symbol}",
            "portfolio": updated_portfolio
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/simulations/run", response_model=SimulationResult)
def run_simulation(
    request: SimulationRequest,
    session: Session = Depends(get_session)
):
    """Run a market scenario simulation on a portfolio"""
    try:
        result = simulation_engine.run_simulation(session, request)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.get("/portfolios/{portfolio_id}/analysis", response_model=PortfolioAnalysis)
def analyze_portfolio(
    portfolio_id: str,
    session: Session = Depends(get_session)
):
    """Analyze portfolio risk and diversification"""
    analysis_data = simulation_engine.analyze_portfolio(session, portfolio_id)
    return PortfolioAnalysis(**analysis_data)

@app.post("/simulations/compare", response_model=ComparisonResult)
def compare_portfolios(
    request: ComparePortfoliosRequest,
    session: Session = Depends(get_session)
):
    """Compare two portfolios under the same scenario"""
    # Run simulation on both portfolios
    sim_request_1 = SimulationRequest(
        portfolio_id=request.portfolio_1_id,
        scenario=request.scenario,
        duration_days=request.duration_days
    )
    sim_request_2 = SimulationRequest(
        portfolio_id=request.portfolio_2_id,
        scenario=request.scenario,
        duration_days=request.duration_days
    )
    
    result_1 = simulation_engine.run_simulation(session, sim_request_1)
    result_2 = simulation_engine.run_simulation(session, sim_request_2)
    
    # Determine winner based on final value
    winner = request.portfolio_1_id if result_1.final_value > result_2.final_value else request.portfolio_2_id
    difference = abs(result_1.final_value - result_2.final_value)
    difference_pct = (difference / result_1.initial_value) * 100
    
    return ComparisonResult(
        portfolio_1_result=result_1,
        portfolio_2_result=result_2,
        winner=winner,
        difference_percentage=difference_pct
    )

@app.get("/assets", response_model=List[Asset])
def list_assets(session: Session = Depends(get_session)):
    """List available assets"""
    statement = select(Asset)
    assets = session.exec(statement).all()
    return list(assets)

@app.get("/assets/{symbol}", response_model=Asset)
def get_asset(symbol: str, session: Session = Depends(get_session)):
    """Get asset by symbol"""
    asset = session.get(Asset, symbol.upper())
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    return asset

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
```

### Step 1.8: Test the FastAPI Server

**1.8.1 Start the server:**
```bash
cd simulation_engine
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**1.8.2 Test endpoints:**
- Visit `http://localhost:8000/docs` for interactive API documentation
- Test creating a portfolio: `POST /portfolios?name=Test%20Portfolio`
- Test running a simulation: `POST /simulations/run` with appropriate JSON body

**1.8.3 Verify Response Format:**
Ensure all endpoints return the expected Pydantic models and that error handling works correctly.

**1.8.4 Test Database Persistence:**
- Create a portfolio
- Make some trades
- Restart the FastAPI server
- Verify that the portfolio and trades persist in `simulator.db`
- This confirms the migration from in-memory storage to database is working correctly

---

## Phase 2: FastMCP AI Bridge Server

### Objective
Build an MCP server that exposes the simulation engine's capabilities to an LLM, enabling conversational, inquiry-based learning.

### Prerequisites
- FastAPI server running (Phase 1)
- Python 3.9+
- Understanding of MCP protocol and FastMCP library

### Step 2.1: Project Structure Setup

Extend the directory structure:

```
project_root/
├── simulation_engine/          # (From Phase 1)
├── mcp_bridge/
│   ├── __init__.py
│   ├── mcp_server.py          # FastMCP server implementation
│   ├── config.py              # Configuration
│   └── prompts.py             # System prompts for AI tutor
├── requirements.txt           # Update with FastMCP
└── README.md
```

**Commands:**
```bash
mkdir -p mcp_bridge
cd mcp_bridge
touch __init__.py mcp_server.py config.py prompts.py
cd ..
```

### Step 2.2: Install FastMCP Dependencies

**2.2.1 Update `requirements.txt`:**
```txt
# ... existing FastAPI dependencies ...

# MCP Dependencies
mcp==1.0.0
fastmcp==0.9.0
httpx==0.25.1  # For calling FastAPI server
```

**2.2.2 Install:**
```bash
pip install -r requirements.txt
```

### Step 2.3: Configuration (`mcp_bridge/config.py`)

```python
import os
from pydantic_settings import BaseSettings

class MCPConfig(BaseSettings):
    """Configuration for MCP Bridge"""
    simulation_api_url: str = "http://localhost:8000"
    api_timeout: int = 30
    
    class Config:
        env_file = ".env"
        env_prefix = "MCP_"

config = MCPConfig()
```

### Step 2.4: System Prompts (`mcp_bridge/prompts.py`)

Define the AI tutor's personality and instructions:

```python
SYSTEM_PROMPT = """You are an expert financial tutor and advisor, specialized in teaching students about stock market dynamics, portfolio management, and risk diversification through hands-on simulation.

Your role is to:
1. Guide students through inquiry-based learning about finance
2. Challenge their assumptions and encourage critical thinking
3. Use the simulation tools available to demonstrate concepts with real data
4. Explain financial concepts in clear, accessible language
5. Encourage students to experiment and learn from mistakes

Teaching Philosophy:
- Use Socratic questioning: Ask thought-provoking questions before giving answers
- Show, don't just tell: Run simulations to demonstrate concepts
- Relate scenarios to real-world events (e.g., "This is similar to what happened in 2008")
- Encourage diversification and risk awareness
- Help students understand the relationship between risk and return

Available Tools:
- You can run market simulations on portfolios
- You can analyze portfolio risk and diversification
- You can compare different portfolios side-by-side
- You can execute trades on behalf of students (with their permission)

When a student asks a question:
1. First, understand their current portfolio state (if applicable)
2. Consider what simulation or analysis would best answer their question
3. Run the appropriate tool
4. Interpret the results and explain them clearly
5. Ask follow-up questions to deepen understanding

Always be encouraging and patient. Remember: you're teaching, not just providing information.
"""

TUTOR_EXAMPLES = """
Example Interactions:

Student: "I put all my money in one stock. Show me why that's risky."
Tutor: "That's an excellent question! Let's run a simulation to see what happens to a concentrated portfolio during a market crash. I'll compare your single-stock portfolio to a diversified one. [runs comparePortfolios with crash scenario] As you can see, your concentrated portfolio lost 85% of its value, while the diversified portfolio only lost 25%. This demonstrates the power of diversification—it protects you from company-specific risks."

Student: "What would happen to my portfolio during a tech bubble?"
Tutor: "Great question! Let's simulate a sector boom scenario on your portfolio. [runs simulation] Notice how the portfolio value grew rapidly initially, but then experienced a sharp correction. This is the classic bubble pattern—unsustainable growth followed by a crash. Your diversification helped mitigate some of the losses."

Student: "How can I reduce my risk?"
Tutor: "Let me first analyze your current portfolio to see where the risks are. [analyzes portfolio] I see you have 80% exposure to technology stocks. Let's run a simulation comparing your current portfolio to one that's more diversified across sectors. [runs comparison] The diversified portfolio has a much lower volatility and better risk-adjusted returns."
"""
```

### Step 2.5: Implement MCP Server (`mcp_bridge/mcp_server.py`)

Create the FastMCP server that bridges the LLM to the simulation engine:

```python
from fastmcp import FastMCP
import httpx
from typing import Dict, Any, List
from mcp_bridge.config import config
from mcp_bridge.prompts import SYSTEM_PROMPT, TUTOR_EXAMPLES

# Initialize FastMCP server
mcp = FastMCP("Financial Tutor MCP Server")

# HTTP client for calling FastAPI
client = httpx.AsyncClient(
    base_url=config.simulation_api_url,
    timeout=config.api_timeout
)

@mcp.tool()
async def runMarketScenario(
    portfolio_id: str,
    scenario: str,
    duration_days: int = 252
) -> Dict[str, Any]:
    """
    Runs a market simulation on a portfolio given a specific scenario.
    
    Args:
        portfolio_id: The ID of the portfolio to simulate
        scenario: One of: "crash", "boom", "bear", "sector_boom", "interest_rate_hike", "panic_sell"
        duration_days: Number of days to simulate (default: 252, which is 1 trading year)
    
    Returns:
        A dictionary containing:
        - initial_value: Starting portfolio value
        - final_value: Ending portfolio value
        - peak_value: Highest value during simulation
        - drawdown: Maximum loss from peak (as percentage)
        - risk_metrics: Sharpe ratio, volatility, total return, max drawdown
        - daily_values: List of portfolio values over time
    
    Example scenarios:
    - "crash": Simulates a major market crash (like 2008)
    - "boom": Simulates a bull market with strong growth
    - "bear": Simulates a bear market with gradual decline
    - "sector_boom": Simulates a sector bubble (like tech bubble)
    - "interest_rate_hike": Simulates market reaction to rising interest rates
    - "panic_sell": Simulates a panic-selling cascade
    """
    try:
        response = await client.post(
            "/simulations/run",
            json={
                "portfolio_id": portfolio_id,
                "scenario": scenario,
                "duration_days": duration_days
            }
        )
        response.raise_for_status()
        result = response.json()
        
        # Format result for LLM consumption
        return {
            "success": True,
            "portfolio_id": portfolio_id,
            "scenario": scenario,
            "initial_value": result["initial_value"],
            "final_value": result["final_value"],
            "peak_value": result["peak_value"],
            "drawdown_percentage": result["drawdown"] * 100,
            "total_return_percentage": result["risk_metrics"]["total_return"] * 100,
            "sharpe_ratio": result["risk_metrics"]["sharpe_ratio"],
            "volatility": result["risk_metrics"]["volatility"],
            "max_drawdown": result["risk_metrics"]["max_drawdown"] * 100,
            "summary": (
                f"Simulation complete: Portfolio started at ${result['initial_value']:,.2f} "
                f"and ended at ${result['final_value']:,.2f} "
                f"(Return: {result['risk_metrics']['total_return']*100:.1f}%). "
                f"Maximum drawdown: {result['drawdown']*100:.1f}%."
            )
        }
    except httpx.HTTPError as e:
        return {
            "success": False,
            "error": f"API error: {str(e)}"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}"
        }

@mcp.tool()
async def analyzePortfolioRisk(portfolio_id: str) -> Dict[str, Any]:
    """
    Analyzes a portfolio's risk level, diversification, and sector exposure.
    
    Args:
        portfolio_id: The ID of the portfolio to analyze
    
    Returns:
        A dictionary containing:
        - total_value: Total portfolio value (cash + investments)
        - cash: Available cash
        - invested_value: Value of all positions
        - diversification_score: Score from 0 (concentrated) to 1 (well-diversified)
        - sector_exposure: Percentage allocation by sector
        - risk_level: "low", "medium", or "high"
        - volatility: Annualized volatility estimate
    
    Use this to:
    - Understand portfolio composition
    - Identify concentration risks
    - Assess diversification quality
    - Get recommendations for improvement
    """
    try:
        response = await client.get(f"/portfolios/{portfolio_id}/analysis")
        response.raise_for_status()
        result = response.json()
        
        return {
            "success": True,
            "portfolio_id": portfolio_id,
            "total_value": result["total_value"],
            "cash": result["cash"],
            "invested_value": result["invested_value"],
            "diversification_score": result["diversification_score"],
            "diversification_interpretation": (
                "Excellent diversification" if result["diversification_score"] > 0.7
                else "Good diversification" if result["diversification_score"] > 0.4
                else "Poor diversification - too concentrated"
            ),
            "sector_exposure": result["sector_exposure"],
            "risk_level": result["risk_level"],
            "volatility": result["volatility"],
            "recommendations": _generate_recommendations(result)
        }
    except httpx.HTTPError as e:
        return {
            "success": False,
            "error": f"API error: {str(e)}"
        }

def _generate_recommendations(analysis: Dict) -> List[str]:
    """Generate recommendations based on analysis"""
    recommendations = []
    
    if analysis["diversification_score"] < 0.4:
        recommendations.append("Consider diversifying across more assets to reduce concentration risk")
    
    if analysis["risk_level"] == "high":
        recommendations.append("Your portfolio has high risk. Consider adding lower-volatility assets")
    
    sector_exposure = analysis["sector_exposure"]
    max_sector = max(sector_exposure.values()) if sector_exposure else 0
    if max_sector > 50:
        recommendations.append(f"You have {max_sector:.1f}% exposure to one sector. Consider sector diversification")
    
    if analysis["cash"] / analysis["total_value"] > 0.5:
        recommendations.append("You're holding a lot of cash. Consider investing more for better returns")
    
    return recommendations

@mcp.tool()
async def comparePortfolios(
    portfolio_1_id: str,
    portfolio_2_id: str,
    scenario: str,
    duration_days: int = 252
) -> Dict[str, Any]:
    """
    Compares two portfolios side-by-side under the same market scenario.
    
    Args:
        portfolio_1_id: ID of the first portfolio
        portfolio_2_id: ID of the second portfolio
        scenario: Market scenario to test (same options as runMarketScenario)
        duration_days: Simulation duration in days
    
    Returns:
        A comparison dictionary showing:
        - Which portfolio performed better
        - Performance difference
        - Individual results for each portfolio
    
    Use this to:
    - Compare different strategies (e.g., "All Tech" vs. "Diversified")
    - Demonstrate the value of diversification
    - Show the impact of different asset allocations
    - Answer "What if" questions about portfolio choices
    """
    try:
        response = await client.post(
            "/simulations/compare",
            json={
                "portfolio_1_id": portfolio_1_id,
                "portfolio_2_id": portfolio_2_id,
                "scenario": scenario,
                "duration_days": duration_days
            }
        )
        response.raise_for_status()
        result = response.json()
        
        return {
            "success": True,
            "scenario": scenario,
            "winner": result["winner"],
            "difference_percentage": result["difference_percentage"],
            "portfolio_1": {
                "id": portfolio_1_id,
                "initial_value": result["portfolio_1_result"]["initial_value"],
                "final_value": result["portfolio_1_result"]["final_value"],
                "return_percentage": result["portfolio_1_result"]["risk_metrics"]["total_return"] * 100
            },
            "portfolio_2": {
                "id": portfolio_2_id,
                "initial_value": result["portfolio_2_result"]["initial_value"],
                "final_value": result["portfolio_2_result"]["final_value"],
                "return_percentage": result["portfolio_2_result"]["risk_metrics"]["total_return"] * 100
            },
            "summary": (
                f"Portfolio comparison: {result['winner']} performed better. "
                f"Portfolio 1 returned {result['portfolio_1_result']['risk_metrics']['total_return']*100:.1f}%, "
                f"while Portfolio 2 returned {result['portfolio_2_result']['risk_metrics']['total_return']*100:.1f}%. "
                f"Difference: {result['difference_percentage']:.1f}%."
            )
        }
    except httpx.HTTPError as e:
        return {
            "success": False,
            "error": f"API error: {str(e)}"
        }

@mcp.tool()
async def createPortfolio(name: str, initial_cash: float = 100000.0) -> Dict[str, Any]:
    """
    Creates a new portfolio for the student.
    
    Args:
        name: Name for the portfolio
        initial_cash: Starting cash amount (default: $100,000)
    
    Returns:
        Portfolio information including ID for future operations
    """
    try:
        response = await client.post(
            f"/portfolios?name={name}&initial_cash={initial_cash}"
        )
        response.raise_for_status()
        result = response.json()
        
        return {
            "success": True,
            "portfolio_id": result["id"],
            "name": result["name"],
            "initial_cash": result["cash"],
            "message": f"Portfolio '{name}' created successfully with ${initial_cash:,.2f}"
        }
    except httpx.HTTPError as e:
        return {
            "success": False,
            "error": f"API error: {str(e)}"
        }

@mcp.tool()
async def executeTrade(
    portfolio_id: str,
    symbol: str,
    quantity: float,
    action: str
) -> Dict[str, Any]:
    """
    Executes a trade (buy or sell) in a portfolio.
    
    Args:
        portfolio_id: ID of the portfolio
        symbol: Stock symbol (e.g., "AAPL", "GOOGL")
        quantity: Number of shares
        action: "buy" or "sell"
    
    Returns:
        Trade execution result and updated portfolio state
    """
    try:
        response = await client.post(
            "/trades",
            json={
                "portfolio_id": portfolio_id,
                "symbol": symbol.upper(),
                "quantity": quantity,
                "action": action.lower()
            }
        )
        response.raise_for_status()
        result = response.json()
        
        portfolio = result["portfolio"]
        return {
            "success": True,
            "message": result["message"],
            "portfolio": {
                "id": portfolio["id"],
                "cash": portfolio["cash"],
                "total_value": sum(
                    pos["asset"]["current_price"] * pos["quantity"]
                    for pos in portfolio["positions"]
                ) + portfolio["cash"],
                "positions": [
                    {
                        "symbol": pos["asset"]["symbol"],
                        "quantity": pos["quantity"],
                        "value": pos["asset"]["current_price"] * pos["quantity"]
                    }
                    for pos in portfolio["positions"]
                ]
            }
        }
    except httpx.HTTPError as e:
        error_detail = "Unknown error"
        if e.response:
            try:
                error_json = e.response.json()
                error_detail = error_json.get("detail", str(e))
            except:
                error_detail = str(e)
        return {
            "success": False,
            "error": f"Trade failed: {error_detail}"
        }

@mcp.tool()
async def getPortfolioInfo(portfolio_id: str) -> Dict[str, Any]:
    """
    Retrieves current state of a portfolio.
    
    Args:
        portfolio_id: ID of the portfolio
    
    Returns:
        Portfolio details including positions and current value
    """
    try:
        response = await client.get(f"/portfolios/{portfolio_id}")
        response.raise_for_status()
        portfolio = response.json()
        
        return {
            "success": True,
            "portfolio_id": portfolio["id"],
            "name": portfolio["name"],
            "cash": portfolio["cash"],
            "total_value": sum(
                pos["asset"]["current_price"] * pos["quantity"]
                for pos in portfolio["positions"]
            ) + portfolio["cash"],
            "positions": [
                {
                    "symbol": pos["asset"]["symbol"],
                    "name": pos["asset"]["name"],
                    "quantity": pos["quantity"],
                    "current_price": pos["asset"]["current_price"],
                    "total_value": pos["asset"]["current_price"] * pos["quantity"]
                }
                for pos in portfolio["positions"]
            ]
        }
    except httpx.HTTPError as e:
        return {
            "success": False,
            "error": f"API error: {str(e)}"
        }

@mcp.tool()
async def listAvailableAssets() -> Dict[str, Any]:
    """
    Lists all available assets that can be traded.
    
    Returns:
        List of assets with symbols, names, types, and sectors
    """
    try:
        response = await client.get("/assets")
        response.raise_for_status()
        assets = response.json()
        
        return {
            "success": True,
            "assets": [
                {
                    "symbol": asset["symbol"],
                    "name": asset["name"],
                    "type": asset["asset_type"],
                    "sector": asset.get("sector", "Unknown"),
                    "current_price": asset["current_price"]
                }
                for asset in assets
            ]
        }
    except httpx.HTTPError as e:
        return {
            "success": False,
            "error": f"API error: {str(e)}"
        }

# Set system prompt for the AI tutor
mcp.set_system_prompt(SYSTEM_PROMPT + "\n\n" + TUTOR_EXAMPLES)

if __name__ == "__main__":
    # Run the MCP server
    mcp.run()
```

### Step 2.6: Server Interaction Explanation

**How the Two Servers Interact:**

1. **User → LLM (MCP Client):** User asks a question like "What would happen to my portfolio during a crash?"

2. **LLM → FastMCP Server:** The LLM recognizes it needs to run a simulation and calls the `runMarketScenario` tool via MCP protocol.

3. **FastMCP Server → FastAPI Server:** The FastMCP server receives the tool call, extracts parameters (portfolio_id, scenario, duration_days), and makes an HTTP POST request to `http://localhost:8000/simulations/run` using `httpx`.

4. **FastAPI Server → FastMCP Server:** The FastAPI server processes the request, runs the simulation logic, and returns JSON results.

5. **FastMCP Server → LLM:** The FastMCP server formats the response and sends it back to the LLM via MCP protocol.

6. **LLM → User:** The LLM interprets the results and explains them to the user in natural language.

**Architecture Diagram:**
```
User
  ↓ (natural language)
LLM (MCP Client, e.g., Claude Desktop)
  ↓ (MCP protocol, tool calls)
FastMCP Server (mcp_bridge/mcp_server.py)
  ↓ (HTTP requests, httpx)
FastAPI Server (simulation_engine/main.py)
  ↓ (computes)
Simulation Engine (Monte Carlo, portfolio calculations)
  ↑ (JSON responses)
```

### Step 2.7: Configure MCP Client

To connect an LLM client (like Claude Desktop) to your MCP server:

**2.7.1 Create MCP Configuration File:**

For Claude Desktop, create/edit: `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "financial-tutor": {
      "command": "python",
      "args": [
        "/absolute/path/to/your/project/mcp_bridge/mcp_server.py"
      ],
      "env": {
        "MCP_SIMULATION_API_URL": "http://localhost:8000"
      }
    }
  }
}
```

**2.7.2 Alternative: Using `mcp run` command:**

You can also run the MCP server directly:
```bash
cd mcp_bridge
python mcp_server.py
```

### Step 2.8: Test the MCP Bridge

**2.8.1 Start FastAPI Server:**
```bash
cd simulation_engine
uvicorn main:app --reload --port 8000
```

**2.8.2 Start MCP Server with FastMCP Inspector:**
```bash
cd mcp_bridge
fastmcp dev mcp_server.py
```

This command will start your MCP server and open the FastMCP Inspector (web UI) where you can:
- Test your tools directly
- See the LLM's "thoughts" and reasoning
- Chat with your AI tutor
- Debug tool calls in real-time

**2.8.3 Alternative: Direct Python execution (for debugging):**
```bash
cd mcp_bridge
python mcp_server.py
```

**2.8.4 Test Tool Calls:**
- Use the FastMCP Inspector (from 2.8.2) or an MCP client (like Claude Desktop) to interact with the server
- Ask questions like "Create a portfolio and analyze its risk"
- Verify that the LLM correctly calls tools and receives results
- Check that portfolios persist in the database after server restarts

---

## Phase 3: Frontend Interface (Optional but Recommended)

### Objective
Build a user-friendly web interface for students to interact with the AI tutor.

### Technologies
- React/Next.js or Vue.js for frontend
- WebSocket or Server-Sent Events for real-time updates
- Connection to MCP client via backend proxy

### Key Features
- Chat interface with AI tutor
- Portfolio visualization dashboard
- Simulation results charts (using Chart.js or D3.js)
- Trade execution interface

### Implementation Steps
1. Set up frontend project structure
2. Create chat UI component
3. Integrate with MCP server via backend proxy
4. Build portfolio visualization components
5. Add simulation results charting
6. Implement responsive design

---

## Phase 4: Educational Framework & User Study

### Objective
Design and implement the educational evaluation framework to validate the tool's effectiveness.

### Step 4.1: Pre-Test Design

**Create Pre-Test Quiz:**
- Questions on financial literacy basics
- Risk diversification understanding
- Market dynamics knowledge
- Portfolio strategy concepts

**Implementation:**
- Create a web form or survey tool
- Store results in a database
- Score and categorize responses

### Step 4.2: Task Design

**Standardized Learning Task:**
- "Build a $100,000 portfolio to save for retirement in 20 years"
- Provide starting conditions (initial cash, available assets)
- Define success criteria

**Implementation:**
- Create task instructions document
- Implement task tracking in simulation engine
- Log all user actions and portfolio changes

### Step 4.3: Post-Test Design

**Create Post-Test Quiz:**
- Same questions as pre-test (for comparison)
- Additional questions on specific scenarios experienced
- Qualitative feedback questions

### Step 4.4: Portfolio Analysis Metrics

**Implement Analysis Functions:**
- Sharpe ratio calculation
- Diversification score (HHI-based)
- Sector exposure analysis
- Risk-adjusted return metrics
- Maximum drawdown analysis

**Compare:**
- Control group (traditional simulator) portfolios
- Test group (AI-assisted) portfolios

### Step 4.5: Data Collection Infrastructure

**Implement Logging:**
- User interactions with AI tutor
- Trades executed
- Simulations run
- Time spent learning
- Questions asked

**Storage:**
- Use a database (PostgreSQL or SQLite) to store:
  - User data (anonymized)
  - Portfolio snapshots
  - Quiz results
  - Interaction logs

---

## Phase 5: Research Paper & Documentation

### Objective
Document the project, analyze results, and prepare research paper.

### Step 5.1: System Documentation

**Technical Documentation:**
- API documentation (auto-generated from FastAPI)
- MCP server documentation
- Architecture diagrams
- Deployment guide

### Step 5.2: Educational Methodology Documentation

**Document:**
- User study protocol
- Ethics approval (if required)
- Data collection methods
- Analysis procedures

### Step 5.3: Results Analysis

**Statistical Analysis:**
- Compare pre-test vs. post-test scores (paired t-test)
- Compare portfolio metrics between groups (independent t-test or Mann-Whitney U)
- Effect size calculations
- Qualitative feedback analysis

### Step 5.4: Paper Writing

**Sections (as outlined in proposal):**
1. Introduction
2. Literature Review
3. System Architecture & Design
4. Experimental Methodology
5. Results
6. Discussion
7. Conclusion & Future Work

**Tools:**
- LaTeX for paper formatting
- Include diagrams (architecture, results charts)
- Cite relevant literature

---

## Phase 6: Testing & Deployment

### Step 6.1: Unit Testing

**Test Coverage:**
- Simulation logic (Monte Carlo accuracy)
- Portfolio operations (trade execution, calculations)
- API endpoints (all CRUD operations)
- MCP tool functions (error handling, data formatting)

**Tools:**
- `pytest` for Python testing
- `httpx` for API testing
- Mock objects for isolated testing

### Step 6.2: Integration Testing

**Test:**
- MCP server → FastAPI server communication
- End-to-end user flows
- Error handling and edge cases

### Step 6.3: Performance Testing

**Optimize:**
- Simulation speed (parallel processing if needed)
- API response times
- Memory usage for large simulations

### Step 6.4: Deployment

**Options:**
- Local deployment (for user study)
- Cloud deployment (AWS, GCP, Azure)
- Containerization (Docker) for easy deployment

**Security:**
- API authentication (if public-facing)
- Rate limiting
- Input validation

---

## Timeline Recommendation

- **Phase 1:** 2-3 weeks
- **Phase 2:** 1-2 weeks
- **Phase 3:** 2-3 weeks (optional)
- **Phase 4:** 3-4 weeks (includes user recruitment and study execution)
- **Phase 5:** 2-3 weeks
- **Phase 6:** 1-2 weeks

**Total Estimated Time:** 11-17 weeks (3-4 months)

---

## Next Steps

1. **Start with Phase 1:** Set up the FastAPI simulation engine
2. **Test thoroughly:** Ensure all endpoints work correctly
3. **Proceed to Phase 2:** Build the MCP bridge
4. **Test integration:** Verify MCP → FastAPI communication
5. **Iterate:** Refine based on initial testing
6. **Scale:** Add more features and complexity as needed

---

## Additional Resources

- FastAPI Documentation: https://fastapi.tiangolo.com/
- FastMCP Documentation: https://github.com/jlowin/fastmcp
- MCP Protocol Spec: https://modelcontextprotocol.io/
- Monte Carlo Simulation: Research papers on financial modeling
- Educational Research Methods: Consult with education research advisor

---

**End of Implementation Plan**

