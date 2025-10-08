"""Tests for configuration loading and validation."""

import pytest
from pydantic import ValidationError

from models.config_models import Config, CredentialsConfig
from utils.config_loader import load_config


class TestCredentialsConfig:
    """Test CredentialsConfig validation."""
    
    def test_valid_credentials(self):
        """Test that valid credentials pass validation."""
        creds = CredentialsConfig(
            github_token="ghp_valid_token",
            supabase_url="https://myproject.supabase.co",
            supabase_key="valid_key_here",
        )
        assert creds.github_token == "ghp_valid_token"
        assert creds.supabase_url == "https://myproject.supabase.co"
        assert creds.supabase_key == "valid_key_here"
    
    def test_rejects_placeholder_github_token(self):
        """Test that placeholder GitHub token is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            CredentialsConfig(
                github_token="ghp_your_token_here",
                supabase_url="https://myproject.supabase.co",
                supabase_key="valid_key",
            )
        assert "GitHub token must be set" in str(exc_info.value)
    
    def test_rejects_placeholder_supabase_url(self):
        """Test that placeholder Supabase URL is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            CredentialsConfig(
                github_token="ghp_valid_token",
                supabase_url="https://your-project.supabase.co",
                supabase_key="valid_key",
            )
        assert "Supabase URL must be set" in str(exc_info.value)
    
    def test_rejects_non_https_supabase_url(self):
        """Test that non-HTTPS Supabase URL is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            CredentialsConfig(
                github_token="ghp_valid_token",
                supabase_url="http://myproject.supabase.co",
                supabase_key="valid_key",
            )
        assert "must start with https://" in str(exc_info.value)
    
    def test_empty_credentials_rejected(self):
        """Test that empty credentials are rejected."""
        with pytest.raises(ValidationError):
            CredentialsConfig(
                github_token="",
                supabase_url="",
                supabase_key="",
            )
    
    def test_optional_llm_keys(self):
        """Test that LLM API keys are optional."""
        creds = CredentialsConfig(
            github_token="ghp_valid_token",
            supabase_url="https://myproject.supabase.co",
            supabase_key="valid_key",
        )
        assert creds.anthropic_api_key is None
        assert creds.openai_api_key is None


class TestConfig:
    """Test main Config model."""
    
    def test_valid_config(self):
        """Test that valid config passes validation."""
        config = Config(
            credentials=CredentialsConfig(
                github_token="ghp_valid_token",
                supabase_url="https://myproject.supabase.co",
                supabase_key="valid_key",
            ),
            log_level="INFO",
        )
        assert config.log_level == "INFO"
        assert config.credentials.github_token == "ghp_valid_token"
    
    def test_log_level_case_insensitive(self):
        """Test that log level is normalized to uppercase."""
        config = Config(
            credentials=CredentialsConfig(
                github_token="ghp_valid_token",
                supabase_url="https://myproject.supabase.co",
                supabase_key="valid_key",
            ),
            log_level="info",
        )
        assert config.log_level == "INFO"
    
    def test_invalid_log_level_rejected(self):
        """Test that invalid log level is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            Config(
                credentials=CredentialsConfig(
                    github_token="ghp_valid_token",
                    supabase_url="https://myproject.supabase.co",
                    supabase_key="valid_key",
                ),
                log_level="INVALID",
            )
        assert "Log level must be one of" in str(exc_info.value)
    
    def test_default_log_level(self):
        """Test that log level defaults to INFO."""
        config = Config(
            credentials=CredentialsConfig(
                github_token="ghp_valid_token",
                supabase_url="https://myproject.supabase.co",
                supabase_key="valid_key",
            )
        )
        assert config.log_level == "INFO"


class TestConfigLoader:
    """Test config_loader.load_config() function."""
    
    def test_load_valid_config(self, test_env):
        """Test loading valid configuration from environment."""
        config = load_config()
        
        assert config.credentials.github_token == test_env["github_token"]
        assert config.credentials.supabase_url == test_env["supabase_url"]
        assert config.credentials.supabase_key == test_env["supabase_key"]
        assert config.log_level == test_env["log_level"]
    
    def test_load_config_with_missing_credentials(self, invalid_env):
        """Test that loading config with missing credentials fails gracefully."""
        with pytest.raises(SystemExit) as exc_info:
            load_config()
        assert exc_info.value.code == 1
