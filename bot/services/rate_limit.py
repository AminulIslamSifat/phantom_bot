
import time
from collections import defaultdict

# user_id -> list of timestamps
_message_timestamps: dict[int, list[float]] = defaultdict(list)

# (max_messages, window_seconds)
_LIMITS: list[tuple[int, int]] = [
    (3, 10),       # burst protection
    (20, 300),     # 5-minute flood
    (40, 3600),    # hourly cap
]


def is_rate_limited(user_id: int) -> bool:
    """Returns True if user exceeded any rate limit tier.
    
    Only call this for text messages — callback queries are exempt.
    """
    now: float = time.time()

    timestamps = _message_timestamps[user_id]

    # Prune entries older than the largest window (1 hour)
    cutoff = now - _LIMITS[-1][1]
    _message_timestamps[user_id] = [ts for ts in timestamps if ts > cutoff]
    timestamps = _message_timestamps[user_id]

    for max_msgs, window in _LIMITS:
        window_cutoff = now - window
        count = sum(1 for ts in timestamps if ts > window_cutoff)
        if count >= max_msgs:
            return True

    _message_timestamps[user_id].append(now)
    return False

