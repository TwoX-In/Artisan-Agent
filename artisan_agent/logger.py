"""Centralized logging configuration for the Artisan Agent system."""

import logging
import os
from pathlib import Path

def setup_logger(name: str = None, log_level: str = "INFO") -> logging.Logger:
    """
    Set up a logger with consistent formatting and handlers.
    
    Args:
        name: Logger name (defaults to calling module's name)
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
    
    Returns:
        Configured logger instance
    """
    if name is None:
        name = __name__
    
    logger = logging.getLogger(name)
    
    # Avoid adding handlers multiple times
    if logger.handlers:
        return logger
    
    # Set log level
    log_level_mapping = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL
    }
    logger.setLevel(log_level_mapping.get(log_level.upper(), logging.INFO))
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler (always present)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler (create logs directory if it doesn't exist)
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    file_handler = logging.FileHandler(log_dir / "artisan_agent.log")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # Component-specific log file
    if name != __name__:
        component_name = name.split('.')[-1]  # Get last part of module name
        component_handler = logging.FileHandler(log_dir / f"{component_name}.log")
        component_handler.setFormatter(formatter)
        logger.addHandler(component_handler)
    
    return logger

def get_logger(name: str = None) -> logging.Logger:
    """
    Get a logger instance for a specific module.
    
    Args:
        name: Module name (will be auto-detected if not provided)
    
    Returns:
        Logger instance
    """
    if name is None:
        # Get the calling module's name
        import inspect
        frame = inspect.currentframe().f_back
        name = frame.f_globals.get('__name__', 'unknown')
    
    return setup_logger(name)

# Environment-based configuration
def configure_logging_from_env():
    """Configure logging based on environment variables."""
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    log_format = os.getenv("LOG_FORMAT", "standard")
    
    if log_format == "json":
        # For structured logging (useful for production)
        formatter = logging.Formatter(
            '{"timestamp":"%(asctime)s","name":"%(name)s","level":"%(levelname)s","message":"%(message)s"}',
            datefmt='%Y-%m-%dT%H:%M:%S'
        )
    else:
        # Standard format
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    
    return formatter, log_level
