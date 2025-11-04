# Running the MCP Server

## Quick Start

1. **Start the FastAPI simulation engine** (in a separate terminal):
   ```bash
   cd /Users/yashk/Desktop/MCP/LY
   python -m simulation_engine.main
   ```
   Or if you have uvicorn installed:
   ```bash
   uvicorn simulation_engine.main:app --reload
   ```
   The FastAPI server should be running on `http://localhost:8000`

2. **Start the MCP Inspector**:
   ```bash
   cd /Users/yashk/Desktop/MCP/LY/mcp_bridge
   mcp dev mcp_server.py
   ```

3. **Access the Inspector**:
   - The command will open your browser automatically
   - Or visit the URL shown in the terminal (usually `http://localhost:6274`)
   - Use the session token from the terminal output for authentication

## Alternative: Run with `mcp run`

If you want to run the server without the inspector UI:

```bash
cd /Users/yashk/Desktop/MCP/LY/mcp_bridge
mcp run mcp_server.py
```

## Troubleshooting

### Error: "Could not import FastMCP"
Install the required package:
```bash
pip install mcp
```

### Error: "Error: typ..." JSON parsing errors
This means something is writing to stdout. The fix has been applied, but if you still see this:
1. Check that you're using the latest version of `mcp_server.py`
2. Make sure all print statements are removed or redirected to stderr
3. Check that no libraries are printing warnings to stdout

### Server not connecting to FastAPI
1. Ensure FastAPI is running on `http://localhost:8000`
2. Check the `MCP_SIMULATION_API_URL` environment variable (defaults to `http://localhost:8000`)
3. Create a `.env` file in `mcp_bridge/` directory if needed:
   ```
   MCP_SIMULATION_API_URL=http://localhost:8000
   ```

## Testing Tools in Inspector

Once the inspector is running:
1. Open the browser UI
2. Select the "Financial Tutor MCP Server" from the server list
3. You'll see all available tools:
   - `createPortfolio` - Create a new portfolio
   - `executeTrade` - Buy or sell assets
   - `getPortfolioInfo` - View portfolio details
   - `runMarketScenario` - Run market simulations
   - `analyzePortfolioRisk` - Analyze portfolio risk
   - `comparePortfolios` - Compare two portfolios
   - `listAvailableAssets` - List all tradable assets
4. Click on any tool to test it with the UI

## Integration with Claude Desktop or Other MCP Clients

To use this server with Claude Desktop, add to your Claude Desktop MCP config:

```json
{
  "mcpServers": {
    "financial-tutor": {
      "command": "uv",
      "args": ["run", "--with", "mcp", "mcp", "run", "mcp_server.py"],
      "cwd": "/Users/yashk/Desktop/MCP/LY/mcp_bridge"
    }
  }
}
```

