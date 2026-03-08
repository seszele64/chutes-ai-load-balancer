from typing import Optional


class ChutesRoutingError(Exception):
    """Base exception for routing errors."""

    pass


class EmptyModelListError(ChutesRoutingError):
    """Raised when no models are configured."""

    pass


class ConfigurationError(ChutesRoutingError):
    """Raised when configuration is invalid."""

    pass


class ModelUnavailableError(ChutesRoutingError):
    """Raised when a model is unavailable."""

    pass


class RateLimitError(ChutesRoutingError):
    """Raised when rate limit is exceeded."""

    pass


class ChutesAPIError(Exception):
    """Base exception for Chutes API errors."""

    pass


class ChutesAPIConnectionError(ChutesAPIError):
    """Raised when connection to Chutes API fails."""

    pass


class ChutesAPITimeoutError(ChutesAPIError):
    """Raised when Chutes API request times out."""

    pass


class DegradationExhaustedError(ChutesRoutingError):
    """Raised when all degradation levels have failed."""

    def __init__(
        self,
        levels_attempted: list,
        original_error: Optional[Exception] = None,
    ):
        self.levels_attempted = levels_attempted
        self.original_error = original_error
        super().__init__(
            f"All degradation levels exhausted: {levels_attempted}. "
            f"Original error: {original_error}"
        )


class CircuitBreakerOpenError(ChutesRoutingError):
    """Raised when circuit breaker is open and degraded response not acceptable."""

    def __init__(self, cooldown_remaining: float):
        self.cooldown_remaining = cooldown_remaining
        super().__init__(f"Circuit breaker open. Retry after {cooldown_remaining:.1f}s")


class MetricsUnavailableError(ChutesRoutingError):
    """Raised when metrics cannot be fetched from the API."""

    pass


class ValidationError(ChutesRoutingError):
    """Raised when request validation fails."""

    pass


class AuthenticationError(ChutesRoutingError):
    """Raised when authentication fails."""

    pass
