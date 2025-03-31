from pathlib import Path
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Settings(BaseSettings):
    """Application settings."""
    
    # API Keys
    OPENAI_API_KEY: str = Field(..., env='OPENAI_API_KEY')
    GOOGLE_API_CREDENTIALS: Path = Field(..., env='GOOGLE_API_CREDENTIALS')
    
    # Model Settings
    MODEL_NAME: str = Field(default="gpt-3.5-turbo", env='MODEL_NAME')
    MAX_TOKENS: int = Field(default=1000, env='MAX_TOKENS')
    
    # Logging
    LOG_LEVEL: str = Field(default="INFO", env='LOG_LEVEL')
    LOG_FILE: Path = Field(default=Path("calendar_agent.log"), env='LOG_FILE')
    
    # Timeouts
    COMMAND_TIMEOUT: int = Field(default=30, env='COMMAND_TIMEOUT')
    
    class Config:
        env_file = ".env"
        case_sensitive = True

# Create global settings instance
settings = Settings() 