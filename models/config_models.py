"""Configuration models for validation using Pydantic."""

from typing import Optional
from pydantic import BaseModel, Field, field_validator


class CredentialsConfig(BaseModel):
    """API credentials loaded from environment variables."""
    
    github_token: str = Field(..., min_length=1, description="GitHub personal access token")
    supabase_url: str = Field(..., min_length=1, description="Supabase project URL")
    supabase_key: str = Field(..., min_length=1, description="Supabase API key")
    database_url: Optional[str] = Field(None, description="PostgreSQL database URL (optional, for schema setup)")
    
    # Optional until we implement LLM classification (Milestone 11)
    anthropic_api_key: Optional[str] = Field(None, description="Anthropic API key for Claude")
    openai_api_key: Optional[str] = Field(None, description="OpenAI API key")
    
    @field_validator("github_token")
    @classmethod
    def validate_github_token(cls, v: str) -> str:
        """Validate GitHub token format."""
        if not v or v == "ghp_your_token_here":
            raise ValueError("GitHub token must be set in .env file")
        return v
    
    @field_validator("supabase_url")
    @classmethod
    def validate_supabase_url(cls, v: str) -> str:
        """Validate Supabase URL format."""
        if not v or v == "https://your-project.supabase.co":
            raise ValueError("Supabase URL must be set in .env file")
        if not v.startswith("https://"):
            raise ValueError("Supabase URL must start with https://")
        return v
    
    @field_validator("supabase_key")
    @classmethod
    def validate_supabase_key(cls, v: str) -> str:
        """Validate Supabase key is set."""
        if not v or v == "your_supabase_anon_key_here":
            raise ValueError("Supabase key must be set in .env file")
        return v


class Config(BaseModel):
    """Application configuration."""
    
    credentials: CredentialsConfig
    log_level: str = Field(default="INFO", description="Logging level")
    
    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level is one of the standard levels."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(f"Log level must be one of: {', '.join(valid_levels)}")
        return v_upper
