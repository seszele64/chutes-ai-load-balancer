"""
LiteLLM Proxy with Chutes Utilization Routing.

A load balancer proxy that routes requests between Chutes AI model
deployments based on real-time utilization data.

Example usage:
    from litellm_proxy import ChutesUtilizationRouting, UtilizationCache
    from litellm_proxy import ChutesAPIClient, ConfigLoader
    from litellm_proxy.exceptions import ChutesRoutingError, ConfigurationError
"""

from litellm_proxy.routing.strategy import ChutesUtilizationRouting
from litellm_proxy.cache.store import UtilizationCache
from litellm_proxy.api.client import ChutesAPIClient
from litellm_proxy.config.loader import ConfigLoader
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

__version__ = "0.1.0"

__all__ = [
    # Core classes
    "ChutesUtilizationRouting",
    "UtilizationCache",
    "ChutesAPIClient",
    "ConfigLoader",
    # Exceptions
    "ChutesRoutingError",
    "EmptyModelListError",
    "ConfigurationError",
    "ModelUnavailableError",
    "RateLimitError",
    "ChutesAPIError",
    "ChutesAPIConnectionError",
    "ChutesAPITimeoutError",
]
