import os
from pydantic_settings import BaseSettings
from pydantic import ConfigDict

class MCPConfig(BaseSettings):
    """Configuration for MCP Bridge"""
    simulation_api_url: str = "http://localhost:8000"
    api_timeout: int = 30
    
    model_config = ConfigDict(
        env_file=".env",
        env_prefix="MCP_"
    )

config = MCPConfig()

