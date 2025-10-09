"""Configuration models for validation using Pydantic."""

from typing import Optional
from pydantic import BaseModel, Field, field_validator, model_validator


class CredentialsConfig(BaseModel):
    """API credentials loaded from environment variables."""
    
    # Platform tokens (at least one required)
    github_token: Optional[str] = Field(None, description="GitHub personal access token (for GitHub repos)")
    gitlab_token: Optional[str] = Field(None, description="GitLab personal access token (for GitLab repos)")
    
    # Supabase (required)
    supabase_url: str = Field(..., min_length=1, description="Supabase project URL")
    supabase_key: str = Field(..., min_length=1, description="Supabase API key")
    database_url: Optional[str] = Field(None, description="PostgreSQL database URL (optional, for schema setup)")
    
    # LLM configuration (Milestones 10-14)
    anthropic_api_key: Optional[str] = Field(None, description="Anthropic API key for Claude")
    openai_api_key: Optional[str] = Field(None, description="OpenAI API key")
    llm_provider: str = Field(default="anthropic", description="LLM provider: 'anthropic' or 'openai'")
    llm_model: str = Field(default="claude-sonnet-4-5-20250929", description="LLM model name")
    
    @model_validator(mode='after')
    def validate_at_least_one_platform_token(self):
        """Ensure at least one platform token is set."""
        if not self.github_token and not self.gitlab_token:
            raise ValueError(
                "At least one platform token must be set: GITHUB_TOKEN or GITLAB_TOKEN. "
                "Set one or both in your .env file depending on which platforms you want to use."
            )
        return self
    
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
