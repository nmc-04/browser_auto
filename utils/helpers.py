"""
Common Helper Functions
"""

import os
import uuid
import re
from datetime import datetime, timezone
from typing import Optional


def generate_id(prefix: str = "wf") -> str:
    """Generates a clean unique ID with prefix."""
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def current_iso_time() -> str:
    """Returns current ISO formatted datetime string."""
    return datetime.now(timezone.utc).isoformat()


def is_valid_url(url: Optional[str]) -> bool:
    """Validates whether a URL has a supported web or local file protocol."""
    if not url or not isinstance(url, str):
        return False
    clean = url.strip()
    return clean.startswith("http://") or clean.startswith("https://") or clean.startswith("file:///") or clean.startswith("file://")


def get_screenshot_dir() -> str:
    """Returns absolute path to screenshot directory, ensuring it exists."""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    screenshot_dir = os.path.join(project_root, "screenshots")
    os.makedirs(screenshot_dir, exist_ok=True)
    return screenshot_dir
