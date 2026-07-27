import time
from collections import defaultdict

# user_id -> list of timestamps
_message_timestamps: dict[int, list[float]] = defaultdict(list)

MAX_MESSAGES: int = 3
WINDOW_SECONDS: int = 10


def is_rate_limited(user_id: int) -> bool:
    """Returns True if user exceeded 3 messages in 10s window."""
    now: float = time.time()
    cutoff: float = now - WINDOW_SECONDS

    # Prune old entries (early return mindset)
    _message_timestamps[user_id] = [
        ts for ts in _message_timestamps[user_id] if ts > cutoff
    ]

    if len(_message_timestamps[user_id]) >= MAX_MESSAGES:
        return True

    _message_timestamps[user_id].append(now)
    return False
