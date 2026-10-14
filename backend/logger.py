import logging
from datetime import datetime
from typing import List, Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("BrowserAutomation")


def format_log(message: str) -> str:
    timestamp = datetime.now().strftime("%H:%M:%S")
    return f"[{timestamp}] {message}"


def add_log_entry(logs_list: List[str], message: str) -> str:
    entry = format_log(message)
    logs_list.append(entry)
    logger.info(message)
    return entry
