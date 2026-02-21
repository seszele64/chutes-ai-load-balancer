"""
Chutes Utilization Routing - Backwards Compatibility Module

DEPRECATED: This module is maintained for backwards compatibility.
Please use the new modular imports instead:
    from litellm_proxy.routing.strategy import ChutesUtilizationRouting
    from litellm_proxy.cache.store import UtilizationCache
    from litellm_proxy.api.client import ChutesAPIClient
    from litellm_proxy.config.loader import ConfigLoader
    from litellm_proxy.exceptions import ChutesRoutingError, ...
"""

# Re-export from new modular location for backwards compatibility
from litellm_proxy.routing.strategy import ChutesUtilizationRouting
from litellm_proxy.exceptions import (
    ChutesRoutingError,
    EmptyModelListError,
    ConfigurationError,
    ModelUnavailableError,
    RateLimitError,
    ChutesAPIError,
    ChutesAPIConnectionError,
    ChutesAPITimeoutError,
)

__all__ = [
    "ChutesUtilizationRouting",
    "ChutesRoutingError",
    "EmptyModelListError",
    "ConfigurationError",
    "ModelUnavailableError",
    "RateLimitError",
    "ChutesAPIError",
    "ChutesAPIConnectionError",
    "ChutesAPITimeoutError",
]
