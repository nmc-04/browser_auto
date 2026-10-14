"""
Application Logging Utility - Secure, Clean & Structured
"""

import logging
import sys
from typing import List

# Configure logger
logger = logging.getLogger("WorkPilot")
logger.setLevel(logging.INFO)

if not logger.handlers:
    try:
        if sys.stdout and hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

from datetime import datetime

# Global in-memory log buffer for frontend inspection
SESSION_LOGS: List[str] = []


def clear_session_logs() -> None:
    """Clears in-memory session log buffer for a fresh execution run."""
    SESSION_LOGS.clear()


def add_log_entry(message: str, level: str = "INFO") -> None:
    """Appends sanitized log line with timestamp and level to memory buffer and outputs to stdout."""
    # Ensure sensitive items like passwords or tokens are scrubbed
    sanitized = message
    for sensitive_keyword in ["password", "token", "secret", "private_key"]:
        if sensitive_keyword in sanitized.lower() and "=" in sanitized:
            parts = sanitized.split("=")
            sanitized = f"{parts[0]}=[REDACTED]"

    # If message doesn't start with a timestamp, prepend one
    if not (len(sanitized) >= 8 and sanitized[2] == ":" and sanitized[5] == ":"):
        timestamp_str = datetime.now().strftime("%H:%M:%S")
        formatted_entry = f"{timestamp_str}  {level.upper().ljust(9)} {sanitized}"
    else:
        formatted_entry = sanitized

    SESSION_LOGS.append(formatted_entry)
    try:
        logger.info(sanitized)
    except Exception:
        try:
            logger.info(sanitized.encode("ascii", "replace").decode("ascii"))
        except Exception:
            pass
