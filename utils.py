"""
Utility functions and classes for GHPL processing.
"""

import time
import threading
from dataclasses import dataclass
from typing import List


@dataclass
class RateLimiter:
    """Thread-safe rate limiter for API calls with optional token limit."""
    max_requests_per_minute: int
    max_tokens_per_minute: int = None
    _requests: List[float] = None
    _token_usage: List[tuple] = None  # List of (timestamp, token_count) tuples
    _lock: threading.Lock = None
    
    def __post_init__(self):
        self._requests = []
        self._token_usage = []
        self._lock = threading.Lock()
    
    def wait_if_needed(self) -> float:
        """Wait if we're approaching rate limit. Returns wait time in seconds."""
        with self._lock:
            now = time.time()
            cutoff = now - 60.0
            
            # Remove requests older than 1 minute
            self._requests = [req_time for req_time in self._requests if req_time > cutoff]
            
            # Remove token usage older than 1 minute
            if self.max_tokens_per_minute is not None:
                self._token_usage = [(timestamp, tokens) for timestamp, tokens in self._token_usage if timestamp > cutoff]
            
            max_wait_time = 0.0
            
            # Check request rate limit
            if len(self._requests) >= self.max_requests_per_minute:
                oldest_request = min(self._requests)
                request_wait_time = 60.0 - (now - oldest_request) + 0.1
                max_wait_time = max(max_wait_time, request_wait_time)
            
            # Check token rate limit if enabled
            if self.max_tokens_per_minute is not None:
                current_tokens = sum(tokens for _, tokens in self._token_usage)
                if current_tokens >= self.max_tokens_per_minute:
                    # Find oldest token usage to determine wait time
                    if self._token_usage:
                        oldest_token_time = min(timestamp for timestamp, _ in self._token_usage)
                        token_wait_time = 60.0 - (now - oldest_token_time) + 0.1
                        max_wait_time = max(max_wait_time, token_wait_time)
            
            if max_wait_time > 0:
                return max_wait_time
            
            # Record this request
            self._requests.append(now)
            return 0.0
    
    def get_current_rate(self) -> float:
        """Get current requests per minute."""
        with self._lock:
            now = time.time()
            cutoff = now - 60.0
            recent_requests = [req_time for req_time in self._requests if req_time > cutoff]
            return len(recent_requests)
    
    def get_current_token_usage(self) -> int:
        """Get current tokens per minute."""
        with self._lock:
            now = time.time()
            cutoff = now - 60.0
            recent_usage = [(timestamp, tokens) for timestamp, tokens in self._token_usage if timestamp > cutoff]
            return sum(tokens for _, tokens in recent_usage)
    
    def record_token_usage(self, tokens: int) -> None:
        """Record token usage for rate limiting."""
        if self.max_tokens_per_minute is not None and tokens > 0:
            with self._lock:
                now = time.time()
                self._token_usage.append((now, tokens))


def wait_for_rate_limit(limiter: RateLimiter, operation: str = "API call") -> None:
    """Wait for rate limiter and show progress."""
    wait_time = limiter.wait_if_needed()
    if wait_time > 0:
        current_rate = limiter.get_current_rate()
        status_msg = f"⏳ Rate limiting: {current_rate}/{limiter.max_requests_per_minute} RPM"
        
        if limiter.max_tokens_per_minute is not None:
            current_tokens = limiter.get_current_token_usage()
            status_msg += f", {current_tokens:,}/{limiter.max_tokens_per_minute:,} TPM"
        
        status_msg += f" - waiting {wait_time:.1f}s for {operation}..."
        print(status_msg)
        time.sleep(wait_time)
        print(f"✅ Rate limit wait complete, proceeding with {operation}")