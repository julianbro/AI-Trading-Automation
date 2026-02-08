"""
Logging utilities for the trading system.
"""
import structlog
import logging
from pathlib import Path
from src.config import config


def setup_logging():
    """Setup structured logging for the trading system."""
    
    # Create logs directory if it doesn't exist
    log_file = Path(config.logging.log_file)
    log_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Configure standard logging
    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, config.logging.level),
        handlers=[
            logging.FileHandler(config.logging.log_file),
            logging.StreamHandler()
        ]
    )
    
    logger = structlog.get_logger(__name__)
    logger.info("Logging initialized", log_file=config.logging.log_file, level=config.logging.level)
