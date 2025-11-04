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

