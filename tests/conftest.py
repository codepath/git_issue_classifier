"""Shared pytest fixtures and configuration."""

import os
import pytest
from pathlib import Path


@pytest.fixture
def test_env(monkeypatch, tmp_path):
    """
    Create a temporary .env file with test credentials.
    
    This fixture sets up valid test environment variables so config
    can be loaded during tests without requiring real credentials.
    """
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test_token_1234567890")
    monkeypatch.setenv("SUPABASE_URL", "https://test-project.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "test_supabase_key_1234567890")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    
    return {
        "github_token": "ghp_test_token_1234567890",
        "supabase_url": "https://test-project.supabase.co",
        "supabase_key": "test_supabase_key_1234567890",
        "log_level": "DEBUG",
    }


@pytest.fixture
def invalid_env(monkeypatch):
    """
    Set up invalid/missing environment variables for testing validation.
    """
    monkeypatch.setenv("GITHUB_TOKEN", "")
    monkeypatch.setenv("SUPABASE_URL", "")
    monkeypatch.setenv("SUPABASE_KEY", "")
