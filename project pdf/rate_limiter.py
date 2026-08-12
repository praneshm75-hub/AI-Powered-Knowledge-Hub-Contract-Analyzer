import time
from typing import Dict, Tuple

class RateLimiter:
    """
    Simulates rate limiting token bucket algorithm for API endpoints.
    Enforces per-IP and per-User rate limits and returns 429 payload metadata.
    """

    def __init__(self, requests_per_minute: int = 10):
        self.requests_per_minute = requests_per_minute
        self.user_requests: Dict[str, list] = {}

    def is_rate_limited(self, client_id: str) -> Tuple[bool, int, Dict[str, str]]:
        now = time.time()
        window = 60 # 60 seconds window

        if client_id not in self.user_requests:
            self.user_requests[client_id] = []

        # Filter out requests older than window
        self.user_requests[client_id] = [t for t in self.user_requests[client_id] if now - t < window]

        if len(self.user_requests[client_id]) >= self.requests_per_minute:
            oldest_request = self.user_requests[client_id][0]
            retry_after = max(1, int(window - (now - oldest_request)))
            headers = {
                "Retry-After": str(retry_after),
                "X-RateLimit-Limit": str(self.requests_per_minute),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(int(now + retry_after))
            }
            return True, retry_after, headers

        self.user_requests[client_id].append(now)
        remaining = self.requests_per_minute - len(self.user_requests[client_id])
        headers = {
            "X-RateLimit-Limit": str(self.requests_per_minute),
            "X-RateLimit-Remaining": str(remaining),
            "X-RateLimit-Reset": str(int(now + window))
        }
        return False, 0, headers
