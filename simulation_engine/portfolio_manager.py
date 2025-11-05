from typing import Dict, List, Optional
from sqlmodel import Session, select
from sqlalchemy.orm import selectinload
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
        """Retrieve portfolio by ID from database with positions eagerly loaded"""
        statement = select(Portfolio).where(Portfolio.id == portfolio_id).options(
            selectinload(Portfolio.positions).selectinload(PortfolioPosition.asset)
        )
        return session.exec(statement).first()
    
    def execute_trade(self, session: Session, trade: TradeRequest, asset: Asset) -> Portfolio:
        """Execute a buy or sell order"""
        portfolio = self.get_portfolio(session, trade.portfolio_id)
        if not portfolio:
            raise ValueError(f"Portfolio {trade.portfolio_id} not found")
        
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
        # Reload portfolio with positions to ensure they're included in serialization
        return self.get_portfolio(session, trade.portfolio_id)
    
    def calculate_diversification_score(self, portfolio: Portfolio) -> float:
        """Calculate diversification score (0-1, where 1 is fully diversified)"""
        if not portfolio.positions:
            return 0.0
        
        # Get position values (positions loaded via relationship)
        total_value = portfolio.total_value()
        if total_value == 0:
            return 0.0
        
        # Ensure all assets are loaded before accessing
        position_weights = []
        for pos in portfolio.positions:
            if not hasattr(pos, 'asset') or pos.asset is None:
                raise ValueError(f"Asset not loaded for position {pos.asset_symbol}")
            position_weights.append(
                (pos.asset.current_price * pos.quantity) / total_value
            )
        
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
            if not hasattr(pos, 'asset') or pos.asset is None:
                raise ValueError(f"Asset not loaded for position {pos.asset_symbol}")
            sector = pos.asset.sector or "Unknown"
            value = pos.asset.current_price * pos.quantity
            sector_values[sector] += value
        
        return {
            sector: (value / total_value) * 100
            for sector, value in sector_values.items()
        }

