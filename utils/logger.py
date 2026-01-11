"""
Logging utilities for the drawing system.
"""
import logging
import sys
from pathlib import Path
from config import LOG_LEVEL, LOG_FILE

_logger = None


def setup_logger(name: str = "drawing_system", level: str = None) -> logging.Logger:
    """Set up and return a logger."""
    global _logger
    
    if _logger is not None:
        return _logger
    
    level = level or LOG_LEVEL
    log_level = getattr(logging, level.upper(), logging.INFO)
    
    logger = logging.getLogger(name)
    logger.setLevel(log_level)
    
    # Avoid duplicate handlers
    if logger.handlers:
        return logger
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)
    
    # File handler
    try:
        file_handler = logging.FileHandler(LOG_FILE)
        file_handler.setLevel(log_level)
        file_format = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_format)
        logger.addHandler(file_handler)
    except Exception as e:
        logger.warning(f"Could not set up file logging: {e}")
    
    _logger = logger
    return logger


def get_logger(name: str = "drawing_system") -> logging.Logger:
    """Get the logger instance."""
    if _logger is None:
        return setup_logger(name)
    return _logger
