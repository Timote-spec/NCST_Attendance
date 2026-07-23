import time
from collections import defaultdict, deque

from app.config import settings


class RateLimiter:
    """Simple in-memory sliding-window limiter keyed by scope+identifier."""

    def __init__(self):
        self._hits: dict[str, deque] = defaultdict(deque)

    def is_allowed(self, key: str, limit: int | None = None, window: int = 60) -> bool:
        limit = limit or settings.rate_limit_per_minute
        now = time.time()
        dq = self._hits[key]
        while dq and dq[0] <= now - window:
            dq.popleft()
        if len(dq) >= limit:
            return False
        dq.append(now)
        return True

    def retry_after(self, key: str, window: int = 60) -> int:
        dq = self._hits.get(key)
        if not dq:
            return 0
        return max(0, int(window - (time.time() - dq[0])) + 1)


limiter = RateLimiter()
