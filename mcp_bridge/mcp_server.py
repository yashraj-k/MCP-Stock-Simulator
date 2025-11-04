import sys
import traceback
import warnings
import os
from contextlib import redirect_stdout, redirect_stderr
from io import StringIO

# MCP protocol requires stdout to only contain JSON-RPC messages
# CRITICAL: Any output to stdout during module load will break JSON-RPC

# Suppress all warnings and redirect to stderr
warnings.filterwarnings("ignore")
def warning_to_stderr(message, category, filename, lineno, file=None, line=None):
    sys.stderr.write(f"Warning: {str(message)}\n")
    sys.stderr.flush()
warnings.showwarning = warning_to_stderr

# Store original stdout/stderr
_original_stdout = sys.stdout
_original_stderr = sys.stderr

# Create a null stdout wrapper to prevent any accidental writes
class NullStdout:
    def write(self, s):
        # Silently discard all writes during initialization
        # Errors should go to stderr, not here
        pass
    def flush(self):
        pass
    def __getattr__(self, name):
        # Forward all other attributes to original stdout
        return getattr(_original_stdout, name)

# Temporarily redirect stdout during imports to catch any accidental prints
# We'll restore it before FastMCP initialization so FastMCP can use stdout for JSON-RPC
_init_stdout_buffer = StringIO()
sys.stdout = _init_stdout_buffer

# Define client here so it's in the global scope
client = None
mcp = None

try:
    # mcp dev REQUIRES mcp.server.fastmcp.FastMCP - check for it first
    # The mcp CLI checks the exact class type and rejects fastmcp.FastMCP
    FastMCP = None
    try:
        from mcp.server.fastmcp import FastMCP  # Required for mcp dev
        FastMCP_class_source = "mcp.server.fastmcp"
    except ImportError:
        try:
            from fastmcp import FastMCP  # Fallback for standalone usage
            FastMCP_class_source = "fastmcp"
            # Warn that this won't work with mcp dev
            sys.stderr.write("Warning: Using fastmcp instead of mcp.server.fastmcp\n")
            sys.stderr.write("This may not work with 'mcp dev'. Install 'mcp' package for full compatibility.\n")
            sys.stderr.flush()
        except ImportError:
            # Write error to stderr, not stdout
            sys.stderr.write("Error: Could not import FastMCP.\n")
            sys.stderr.write("For 'mcp dev': pip install mcp\n")
            sys.stderr.write("For standalone: pip install fastmcp\n")
            sys.stderr.flush()
            sys.stdout = _original_stdout  # Restore before exit
            sys.exit(1)
    
    if FastMCP is None:
        sys.stderr.write("Error: FastMCP import failed\n")
        sys.stderr.flush()
        sys.stdout = _original_stdout  # Restore before exit
        sys.exit(1)
    
    import httpx
    from typing import Dict, Any, List
    
    # Import local modules - catch any errors
    try:
        # --- THIS IS THE FIX ---
        # Use direct imports, not relative, as this is run as a script
        from config import config
        from prompts import SYSTEM_PROMPT, TUTOR_EXAMPLES
        # --- END FIX ---
    except Exception as e:
        sys.stderr.write(f"Error importing config or prompts: {str(e)}\n")
        traceback.print_exc(file=sys.stderr)
        sys.stderr.flush()
        sys.stdout = _original_stdout  # Restore before exit
        sys.exit(1)
    
    # Restore stdout BEFORE FastMCP initialization
    # FastMCP needs stdout for JSON-RPC protocol
    sys.stdout = _original_stdout
    
    # Check if anything was accidentally printed during imports
    captured_output = _init_stdout_buffer.getvalue()
    if captured_output:
        # If something was printed, it's a problem - log it to stderr
        sys.stderr.write(f"WARNING: Captured stdout output during imports: {repr(captured_output)}\n")
        sys.stderr.flush()
    
    # Initialize FastMCP server
    # FastMCP will use stdout for JSON-RPC messages
    try:
        mcp = FastMCP("Financial Tutor MCP Server")
    except Exception as e:
        sys.stderr.write(f"Error creating FastMCP server: {str(e)}\n")
        traceback.print_exc(file=sys.stderr)
        sys.stderr.flush()
        sys.exit(1)

    # --- MOVED THIS BLOCK INSIDE THE MAIN TRY...EXCEPT ---
    # HTTP client for calling FastAPI
    try:
        if not config.simulation_api_url:
            raise ValueError("MCP_SIMULATION_API_URL is not set in .env file")
            
        client = httpx.AsyncClient(
            base_url=config.simulation_api_url,
            timeout=config.api_timeout
        )
    except Exception as e:
        sys.stderr.write(f"Error creating HTTP client: {str(e)}\n")
        traceback.print_exc(file=sys.stderr)
        sys.stderr.flush()
        sys.exit(1) # <-- Gracefully exit instead of re-raising
    # --- END MOVED BLOCK ---

except Exception as e:
    # Any error during initialization goes to stderr
    sys.stderr.write(f"Error initializing MCP server: {str(e)}\n")
    traceback.print_exc(file=sys.stderr)
    sys.stderr.flush()
    if sys.stdout != _original_stdout:
        sys.stdout = _original_stdout  # Restore before exit
    sys.exit(1)


# --- All Tool Definitions Go Here (Unchanged) ---
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
    
    if analysis.get("diversification_score", 1.0) < 0.4:
        recommendations.append("Consider diversifying across more assets to reduce concentration risk")
    
    if analysis.get("risk_level") == "high":
        recommendations.append("Your portfolio has high risk. Consider adding lower-volatility assets")
    
    sector_exposure = analysis.get("sector_exposure", {})
    max_sector = max(sector_exposure.values()) if sector_exposure else 0
    if max_sector > 50:
        recommendations.append(f"You have {max_sector:.1f}% exposure to one sector. Consider sector diversification")
    
    total_value = analysis.get("total_value", 0)
    cash = analysis.get("cash", 0)
    
    # Check for division by zero if total_value is 0
    if total_value > 0 and (cash / total_value > 0.5):
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
        # Note: Calling the /trades endpoint as recommended in the review
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
        
        # Safely get positions (default to empty list if missing)
        positions = portfolio.get("positions", [])
        
        # Calculate total value from positions
        total_value = portfolio["cash"] + sum(
            pos["asset"]["current_price"] * pos["quantity"]
            for pos in positions
        )

        return {
            "success": True,
            "message": result["message"],
            "portfolio": {
                "id": portfolio["id"],
                "cash": portfolio["cash"],
                "total_value": total_value,
                "positions": [
                    {
                        "symbol": pos["asset"]["symbol"],
                        "quantity": pos["quantity"],
                        "value": pos["asset"]["current_price"] * pos["quantity"]
                    }
                    for pos in positions
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
        
        # Safely get positions (default to empty list if missing)
        positions = portfolio.get("positions", [])
        
        # Calculate total value from positions
        total_value = portfolio["cash"] + sum(
            pos["asset"]["current_price"] * pos["quantity"]
            for pos in positions
        )
        
        return {
            "success": True,
            "portfolio_id": portfolio["id"],
            "name": portfolio["name"],
            "cash": portfolio["cash"],
            "total_value": total_value,
            "positions": [
                {
                    "symbol": pos["asset"]["symbol"],
                    "name": pos["asset"]["name"],
                    "quantity": pos["quantity"],
                    "current_price": pos["asset"]["current_price"],
                    "total_value": pos["asset"]["current_price"] * pos["quantity"]
                }
                for pos in positions
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

# --- SAFER SYSTEM PROMPT BLOCK ---
# We must set this *after* all tools are defined
try:
    if hasattr(mcp, 'system_prompt'):
        # Check that prompts were imported successfully before concatenating
        if SYSTEM_PROMPT is not None and TUTOR_EXAMPLES is not None:
            mcp.system_prompt = SYSTEM_PROMPT + "\n\n" + TUTOR_EXAMPLES
        else:
            sys.stderr.write("Warning: SYSTEM_PROMPT or TUTOR_EXAMPLES not loaded. Using default prompt.\n")
            sys.stderr.flush()
except Exception as e:
    # Catch any errors during prompt setting (e.g., TypeError)
    sys.stderr.write(f"Warning: Could not set system prompt: {str(e)}\n")
    sys.stderr.flush()
    # This is not a fatal error, so we continue
    pass


# FastMCP servers are automatically run by the MCP CLI (mcp run or mcp dev)
# The mcp object is exposed at module level for the CLI to discover and run
# When the script is executed directly, FastMCP handles stdio automatically

