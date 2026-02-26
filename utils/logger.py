import logging
import sys
import json
import traceback
from logging.handlers import RotatingFileHandler
import os
import colorama
from datetime import datetime

colorama.init(autoreset=True)

class JSONFormatter(logging.Formatter):
    """
    Formatter that outputs JSON strings for easier parsing by monitoring tools.
    """
    def format(self, record):
        log_obj = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "func": record.funcName,
            "line": record.lineno
        }
        
        if record.exc_info:
            log_obj["exception"] = traceback.format_exception(*record.exc_info)
            
        return json.dumps(log_obj)

class ColoredFormatter(logging.Formatter):
    """Custom formatter with colors for console output."""
    
    COLORS = {
        logging.DEBUG: colorama.Fore.CYAN,
        logging.INFO: colorama.Fore.GREEN,
        logging.WARNING: colorama.Fore.YELLOW,
        logging.ERROR: colorama.Fore.RED,
        logging.CRITICAL: colorama.Fore.RED + colorama.Style.BRIGHT,
    }

    def format(self, record):
        color = self.COLORS.get(record.levelno, "")
        message = super().format(record)
        return f"{color}{message}{colorama.Style.RESET_ALL}"

def setup_logging(log_level=logging.INFO, log_file="system.log", json_format=False):
    """
    Sets up the centralized logging configuration.
    """
    # Create logger
    logger = logging.getLogger()
    logger.setLevel(log_level)
    
    # Clear existing handlers
    if logger.handlers:
        logger.handlers = []

    # Formatters
    console_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(ColoredFormatter(console_format, datefmt="%H:%M:%S"))
    logger.addHandler(console_handler)
    
    # File Handler
    file_handler = RotatingFileHandler(log_file, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG) # Always log debug to file
    
    if json_format:
        file_handler.setFormatter(JSONFormatter())
    else:
        file_handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
        
    logger.addHandler(file_handler)
    
    logging.info(f"Logging initialized. Level: {logging.getLevelName(log_level)}")
    return logger
