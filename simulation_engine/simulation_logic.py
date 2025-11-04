import numpy as np
from typing import List, Dict
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

