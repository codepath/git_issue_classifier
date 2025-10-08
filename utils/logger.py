"""Logging setup for the application."""

import logging
import sys


def setup_logger(log_level: str = "INFO", name: str = "git_issue_classifier") -> logging.Logger:
    """
    Set up and configure application logger.
    
    Creates a logger with a simple, readable format suitable for CLI output.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        name: Logger name (default: git_issue_classifier)
        
    Returns:
        logging.Logger: Configured logger instance
    """
    # Convert string to logging level
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    
    # Configure root logger
    logging.basicConfig(
        level=numeric_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        stream=sys.stdout,
        force=True,  # Override any existing configuration
    )
    
    # Get named logger and set its level explicitly
    logger = logging.getLogger(name)
    logger.setLevel(numeric_level)
    
    return logger
