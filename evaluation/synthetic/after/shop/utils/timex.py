"""Date/time utilities (kept: actually used by auth and orders)."""
from datetime import datetime, timezone


def utcnow():
    return datetime.now(timezone.utc).isoformat()
