import logging
from typing import Any, Dict, Optional
from datetime import datetime
from pathlib import Path
import json

from config import settings

# Configure logging
logging.basicConfig(
    level=settings.log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename=settings.log_file
)
logger = logging.getLogger(__name__)

def safe_load_json(file_path: Path) -> Optional[Dict[str, Any]]:
    """Safely load JSON from a file."""
    try:
        if not file_path.exists():
            logger.error(f"File not found: {file_path}")
            return None
        
        with open(file_path, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON from {file_path}: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Error reading file {file_path}: {str(e)}")
        return None

def format_datetime(dt: datetime) -> str:
    """Format datetime object to string."""
    return dt.strftime("%Y-%m-%d %H:%M:%S")

def parse_datetime(dt_str: str) -> Optional[datetime]:
    """Parse datetime string to datetime object."""
    try:
        return datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        logger.error(f"Invalid datetime string: {dt_str}")
        return None

def ensure_directory(path: Path) -> bool:
    """Ensure a directory exists, create if it doesn't."""
    try:
        path.mkdir(parents=True, exist_ok=True)
        return True
    except Exception as e:
        logger.error(f"Error creating directory {path}: {str(e)}")
        return False

def validate_email(email: str) -> bool:
    """Validate email format."""
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

def truncate_text(text: str, max_length: int = 100) -> str:
    """Truncate text to specified length."""
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..." 