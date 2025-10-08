"""Tests for logger setup."""

import logging
from utils.logger import setup_logger


def test_setup_logger_default():
    """Test logger setup with default settings."""
    logger = setup_logger()
    assert logger.name == "git_issue_classifier"
    assert logger.level == logging.INFO


def test_setup_logger_custom_level():
    """Test logger setup with custom log level."""
    logger = setup_logger(log_level="DEBUG")
    assert logger.level == logging.DEBUG


def test_setup_logger_custom_name():
    """Test logger setup with custom name."""
    logger = setup_logger(name="test_logger")
    assert logger.name == "test_logger"


def test_logger_level_case_insensitive():
    """Test that log level string is case insensitive."""
    logger = setup_logger(log_level="debug")
    assert logger.level == logging.DEBUG
    
    logger = setup_logger(log_level="INFO")
    assert logger.level == logging.INFO
