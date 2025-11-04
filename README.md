# AI-Assisted Financial Tutor

A novel stock market simulator using Model Context Protocol (MCP) for inquiry-based financial education.

## Overview

This project integrates a FastAPI-based financial simulation engine with a FastMCP AI bridge to create an educational tool where students can learn about finance through conversational interaction with an AI tutor.

## Architecture

- **Simulation Engine (FastAPI)**: Robust API-driven stock market simulator with probabilistic modeling
- **AI Bridge (FastMCP)**: MCP server that exposes simulation capabilities to LLMs
- **Database (SQLite + SQLModel)**: Persistent storage for portfolios, positions, and assets

## Quick Start

### Prerequisites

- Python 3.9+
- pip or poetry

### Installation

1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On macOS/Linux
# OR
venv\Scripts\activate  # On Windows
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Start the FastAPI simulation engine:
```bash
cd simulation_engine
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

4. In a separate terminal, start the MCP server:
```bash
cd mcp_bridge
fastmcp dev mcp_server.py
```

### Testing the API

Visit `http://localhost:8000/docs` for interactive API documentation.

## Project Structure

```
LY/
├── simulation_engine/
│   ├── __init__.py
│   ├── main.py              # FastAPI application
│   ├── models.py            # SQLModel models
│   ├── simulation_logic.py  # Core simulation algorithms
│   ├── portfolio_manager.py # Portfolio operations
│   └── market_model.py      # Market dynamics engine
├── mcp_bridge/
│   ├── __init__.py
│   ├── mcp_server.py        # FastMCP server
│   ├── config.py            # Configuration
│   └── prompts.py           # AI tutor prompts
├── requirements.txt
└── README.md
```

## Key Features

- **Persistent Database**: Portfolios persist across server restarts (SQLite)
- **Market Scenarios**: Crash, boom, bear markets, sector bubbles, etc.
- **Portfolio Analysis**: Risk assessment, diversification scoring, sector exposure
- **MCP Integration**: AI tutor can execute trades, run simulations, and analyze portfolios

## Developer Notes

This implementation includes simplified models for educational purposes:
- **Market Model**: Uses discrete price jumps rather than true systemic cascades
- **Volatility**: Hardcoded for simplicity (production would use covariance matrices)

See the code comments for details on these simplifications.

## Next Steps

See `IMPLEMENTATION_PLAN.md` for detailed implementation phases and remaining components (frontend, user study, research paper).

