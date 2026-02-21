"""
Custom exceptions for LiteLLM Proxy.

This module defines the exception hierarchy used throughout the
litellm_proxy package for error handling.
"""


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
