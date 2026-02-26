"""
Logging configuration
"""
import logging
import sys

_configured = False

def get_logger(name: str):
    """Get a logger instance"""
    global _configured
    
    if not _configured:
        # Simple logging setup
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[logging.StreamHandler(sys.stdout)]
        )
        _configured = True
    
    return logging.getLogger(name)