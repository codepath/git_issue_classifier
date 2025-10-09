"""Configuration loader that reads from .env and validates with Pydantic."""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from pydantic import ValidationError

from models.config_models import Config, CredentialsConfig


def load_config() -> Config:
    """
    Load and validate configuration from environment variables.
    
    Reads from .env file in the project root and validates all required
    credentials and settings using Pydantic models.
    
    Returns:
        Config: Validated configuration object
        
    Raises:
        SystemExit: If configuration is invalid or missing required fields
    """
    # Load .env file from project root
    env_path = Path(__file__).parent.parent / ".env"
    load_dotenv(dotenv_path=env_path)
    
    try:
        config = Config(
            credentials=CredentialsConfig(
                github_token=os.getenv("GITHUB_TOKEN"),
                gitlab_token=os.getenv("GITLAB_TOKEN"),
                supabase_url=os.getenv("SUPABASE_URL", ""),
                supabase_key=os.getenv("SUPABASE_KEY", ""),
                database_url=os.getenv("DATABASE_URL"),
                anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
                openai_api_key=os.getenv("OPENAI_API_KEY"),
            ),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
        )
        
        return config
        
    except ValidationError as e:
        print("❌ Configuration validation failed:", file=sys.stderr)
        print("\nPlease check your .env file. Missing or invalid fields:", file=sys.stderr)
        
        for error in e.errors():
            field_path = " → ".join(str(x) for x in error["loc"])
            message = error["msg"]
            print(f"  • {field_path}: {message}", file=sys.stderr)
        
        print("\nHint: Copy .env.example to .env and fill in your credentials.", file=sys.stderr)
        sys.exit(1)
