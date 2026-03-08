"""
Configuration module for intelligent multi-metric routing.

This module handles configuration loading from YAML files and environment variables.
"""

import os
import logging
from typing import Optional, Dict, Any

from litellm_proxy.routing.strategy import RoutingStrategy, StrategyWeights
from litellm_proxy.routing.cache import MetricsCache

logger = logging.getLogger(__name__)


class RoutingConfig:
    """
    Configuration for intelligent multi-metric routing.

    Supports loading from:
    - YAML configuration files
    - Environment variables
    - Default values
    """

    DEFAULT_STRATEGY = RoutingStrategy.BALANCED
    DEFAULT_CACHE_TTL_UTILIZATION = 30
    DEFAULT_CACHE_TTL_TPS = 300
    DEFAULT_CACHE_TTL_TTFT = 300
    DEFAULT_CACHE_TTL_QUALITY = 300

    def __init__(
        self,
        strategy: Optional[RoutingStrategy] = None,
        custom_weights: Optional[StrategyWeights] = None,
        cache_ttls: Optional[Dict[str, int]] = None,
        chutes_api_url: str = "https://api.chutes.ai",
        high_utilization_threshold: float = 0.8,
    ):
        self.strategy = strategy or self.DEFAULT_STRATEGY
        self.custom_weights = custom_weights
        self.cache_ttls = cache_ttls or {
            "utilization": self.DEFAULT_CACHE_TTL_UTILIZATION,
            "tps": self.DEFAULT_CACHE_TTL_TPS,
            "ttft": self.DEFAULT_CACHE_TTL_TTFT,
            "quality": self.DEFAULT_CACHE_TTL_QUALITY,
        }
        self.chutes_api_url = chutes_api_url
        self.high_utilization_threshold = high_utilization_threshold

    @classmethod
    def from_env(cls) -> "RoutingConfig":
        """Create configuration from environment variables."""
        # Get strategy from env
        strategy_str = os.environ.get("ROUTING_STRATEGY", "balanced")
        strategy = RoutingStrategy.from_string(strategy_str)

        # Get custom weights from env (if all are set)
        custom_weights = None
        if all(
            os.environ.get(f"ROUTING_{w.upper()}_WEIGHT")
            for w in ["tps", "ttft", "quality", "utilization"]
        ):
            custom_weights = StrategyWeights.from_env()

        # Get cache TTLs from env
        cache_ttls = {
            "utilization": int(
                os.environ.get(
                    "CACHE_TTL_UTILIZATION", cls.DEFAULT_CACHE_TTL_UTILIZATION
                )
            ),
            "tps": int(os.environ.get("CACHE_TTL_TPS", cls.DEFAULT_CACHE_TTL_TPS)),
            "ttft": int(os.environ.get("CACHE_TTL_TTFT", cls.DEFAULT_CACHE_TTL_TTFT)),
            "quality": int(
                os.environ.get("CACHE_TTL_QUALITY", cls.DEFAULT_CACHE_TTL_QUALITY)
            ),
        }

        # Get API URL
        chutes_api_url = os.environ.get("CHUTES_API_URL", "https://api.chutes.ai")

        # Get high utilization threshold
        threshold = float(os.environ.get("HIGH_UTILIZATION_THRESHOLD", "0.8"))

        return cls(
            strategy=strategy,
            custom_weights=custom_weights,
            cache_ttls=cache_ttls,
            chutes_api_url=chutes_api_url,
            high_utilization_threshold=threshold,
        )

    @classmethod
    def from_yaml(cls, config: Dict[str, Any]) -> "RoutingConfig":
        """Create configuration from YAML config dictionary."""
        router_settings = config.get("router_settings", {})

        # Get strategy
        strategy_str = router_settings.get("routing_strategy", "balanced")
        strategy = RoutingStrategy.from_string(strategy_str)

        # Get custom weights
        custom_weights = None
        weights_config = router_settings.get("routing_weights")
        if weights_config:
            custom_weights = StrategyWeights(
                tps=weights_config.get("tps", 0.25),
                ttft=weights_config.get("ttft", 0.25),
                quality=weights_config.get("quality", 0.25),
                utilization=weights_config.get("utilization", 0.25),
            )

        # Get cache TTLs
        cache_ttls_config = router_settings.get("cache_ttls", {})
        cache_ttls = {
            "utilization": cache_ttls_config.get(
                "utilization", cls.DEFAULT_CACHE_TTL_UTILIZATION
            ),
            "tps": cache_ttls_config.get("tps", cls.DEFAULT_CACHE_TTL_TPS),
            "ttft": cache_ttls_config.get("ttft", cls.DEFAULT_CACHE_TTL_TTFT),
            "quality": cache_ttls_config.get("quality", cls.DEFAULT_CACHE_TTL_QUALITY),
        }

        # Get API URL
        chutes_api_url = router_settings.get("chutes_api_url", "https://api.chutes.ai")

        # Get threshold
        threshold = router_settings.get("high_utilization_warning_threshold", 0.8)

        return cls(
            strategy=strategy,
            custom_weights=custom_weights,
            cache_ttls=cache_ttls,
            chutes_api_url=chutes_api_url,
            high_utilization_threshold=threshold,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "strategy": self.strategy.value,
            "custom_weights": self.custom_weights.to_dict()
            if self.custom_weights
            else None,
            "cache_ttls": self.cache_ttls,
            "chutes_api_url": self.chutes_api_url,
            "high_utilization_threshold": self.high_utilization_threshold,
        }


def load_routing_config(config: Optional[Dict[str, Any]] = None) -> RoutingConfig:
    """
    Load routing configuration.

    Priority: env vars > YAML config > defaults

    Args:
        config: Optional YAML config dictionary

    Returns:
        RoutingConfig instance
    """
    # First try environment variables (highest priority)
    if os.environ.get("ROUTING_STRATEGY"):
        logger.info("Loading routing config from environment variables")
        return RoutingConfig.from_env()

    # Then try YAML config
    if config:
        logger.info("Loading routing config from YAML")
        return RoutingConfig.from_yaml(config)

    # Default
    logger.info("Using default routing config")
    return RoutingConfig()
