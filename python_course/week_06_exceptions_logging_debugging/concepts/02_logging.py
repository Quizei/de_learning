"""
Logging in Python
=================
Production-grade logging for applications.
"""

import logging
import sys
from datetime import datetime

# ================================
# BASIC LOGGING
# ================================

# Configure basic logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

print("--- Logging Levels ---")
logger.debug("Debug message - detailed info for debugging")
logger.info("Info message - confirmation that things work")
logger.warning("Warning message - something unexpected")
logger.error("Error message - serious problem")
logger.critical("Critical message - program may crash")

# ================================
# CUSTOM LOGGER CONFIGURATION
# ================================

def setup_logger(name, log_file=None, level=logging.INFO):
    """Create a configured logger."""
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_format = logging.Formatter('%(levelname)s - %(message)s')
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)

    # File handler (optional)
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(level)
        file_format = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(file_format)
        logger.addHandler(file_handler)

    return logger

# ================================
# STRUCTURED LOGGING
# ================================

print("\n--- Structured Logging ---")

import json

class JSONFormatter(logging.Formatter):
    """Format logs as JSON."""
    def format(self, record):
        log_obj = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
        }
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_obj)

# ================================
# LOGGING WITH CONTEXT
# ================================

print("\n--- Logging with Extra Context ---")

# Using extra parameter
logger.info("User action", extra={"user_id": 123, "action": "login"})

# Using LoggerAdapter for consistent extra fields
class ContextLogger(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        return f"[{self.extra['request_id']}] {msg}", kwargs

ctx_logger = ContextLogger(logger, {"request_id": "abc-123"})
ctx_logger.info("Processing request")

# ================================
# EXCEPTION LOGGING
# ================================

print("\n--- Exception Logging ---")

try:
    result = 1 / 0
except ZeroDivisionError:
    logger.exception("Division failed")  # Includes traceback

# ================================
# BEST PRACTICES
# ================================

print("\n--- Best Practices ---")
print("""
1. Use appropriate log levels
2. Include context (user_id, request_id, etc.)
3. Don't log sensitive data (passwords, tokens)
4. Use structured logging for production
5. Configure log rotation for files
6. Use logger.exception() for errors with tracebacks
7. Create logger per module: logger = logging.getLogger(__name__)
""")

print("\n✅ Logging complete!")
