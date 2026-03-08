"""
Circuit Breaker for Chutes API calls.

This module provides an API-level circuit breaker that prevents cascading
failures by stopping API calls when the service is experiencing issues.
"""

import logging
import threading
import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, return degraded
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""

    failure_threshold: int = 3
    cooldown_seconds: int = 30
    half_open_timeout: int = 10


class CircuitBreaker:
    """
    API-level circuit breaker for Chutes API calls.

    Prevents cascading failures by stopping API calls when
    the service is experiencing issues.
    """

    def __init__(self, config: Optional[CircuitBreakerConfig] = None):
        self.config = config or CircuitBreakerConfig()
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: Optional[float] = None
        self._lock = threading.RLock()
        self._last_success_time: Optional[float] = None

    @property
    def state(self) -> CircuitState:
        """Get current circuit state, checking for cooldown expiration."""
        with self._lock:
            if self._state == CircuitState.OPEN:
                if self._last_failure_time:
                    elapsed = time.time() - self._last_failure_time
                    if elapsed >= self.config.cooldown_seconds:
                        self._state = CircuitState.HALF_OPEN
                        logger.info("Circuit breaker transitioning to HALF_OPEN")
            return self._state

    def is_open(self) -> bool:
        """Check if circuit is open (returns degraded responses)."""
        return self.state == CircuitState.OPEN

    def is_half_open(self) -> bool:
        """Check if circuit is half-open (testing recovery)."""
        return self.state == CircuitState.HALF_OPEN

    def record_success(self) -> None:
        """Record successful API call."""
        with self._lock:
            self._last_success_time = time.time()
            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.CLOSED
                self._failure_count = 0
                logger.info("Circuit breaker CLOSED after successful recovery")
            else:
                self._failure_count = 0

    def record_failure(self) -> None:
        """Record failed API call."""
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()

            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.OPEN
                logger.warning("Circuit breaker OPEN after half-open failure")
            elif self._failure_count >= self.config.failure_threshold:
                self._state = CircuitState.OPEN
                logger.warning(
                    f"Circuit breaker OPEN after {self._failure_count} failures"
                )

    def get_status(self) -> dict:
        """Get circuit breaker status for debugging."""
        with self._lock:
            return {
                "state": self.state.value,
                "failure_count": self._failure_count,
                "last_failure_time": self._last_failure_time,
                "last_success_time": self._last_success_time,
            }

    def get_cooldown_remaining(self) -> float:
        """Get remaining cooldown time in seconds."""
        with self._lock:
            if self._state != CircuitState.OPEN or not self._last_failure_time:
                return 0.0
            elapsed = time.time() - self._last_failure_time
            remaining = self.config.cooldown_seconds - elapsed
            return max(0.0, remaining)

    def reset(self) -> None:
        """Reset the circuit breaker to closed state."""
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._last_failure_time = None
            self._last_success_time = None
            logger.info("Circuit breaker manually reset to CLOSED")
