"""
Chutes Utilization Routing Strategy for LiteLLM.

This module provides the routing strategy that routes requests to the
least utilized Chutes deployment based on real-time utilization data.
"""

import logging
import os
from typing import Optional, Union, List, Dict, Any

from litellm import CustomRoutingStrategyBase

from litellm_proxy.api.client import ChutesAPIClient
from litellm_proxy.cache.store import UtilizationCache
from litellm_proxy.exceptions import (
    ChutesRoutingError,
    EmptyModelListError,
)

logger = logging.getLogger(__name__)


class ChutesUtilizationRouting(CustomRoutingStrategyBase):
    """
    Custom routing strategy that routes requests to the least utilized
    Chutes deployment based on real-time utilization data.

    This strategy:
    1. Fetches utilization data from Chutes API for each deployment
    2. Caches the utilization data with configurable TTL
    3. Routes requests to the deployment with the lowest utilization
    4. Falls back to default behavior if API is unavailable

    The strategy uses dependency injection for the API client and cache,
    making it easy to test and swap implementations.
    """

    def __init__(
        self,
        chutes_api_key: Optional[str] = None,
        cache_ttl: int = 30,
        chutes_api_base: str = "https://api.chutes.ai",
        api_client: Optional[ChutesAPIClient] = None,
        cache: Optional[UtilizationCache] = None,
    ):
        """
        Initialize the Chutes utilization routing strategy.

        Args:
            chutes_api_key: API key for Chutes API. Falls back to CHUTES_API_KEY env var.
            cache_ttl: Time-to-live for cache entries in seconds (default: 30)
            chutes_api_base: Base URL for Chutes API (default: https://api.chutes.ai)
            api_client: Optional ChutesAPIClient instance (for dependency injection)
            cache: Optional UtilizationCache instance (for dependency injection)
        """
        self.chutes_api_key = chutes_api_key or os.environ.get("CHUTES_API_KEY")
        self.cache_ttl = cache_ttl
        self.chutes_api_base = chutes_api_base
        self.router = None  # Reference to the Router instance, set via set_router()

        # Use injected dependencies or create default instances
        self._api_client = api_client
        self._cache = cache

        logger.info(
            f"ChutesUtilizationRouting initialized with cache_ttl={cache_ttl}s, "
            f"api_base={chutes_api_base}"
        )

    @property
    def api_client(self) -> ChutesAPIClient:
        """Get or create the API client."""
        if self._api_client is None:
            self._api_client = ChutesAPIClient(
                api_key=self.chutes_api_key,
                base_url=self.chutes_api_base,
                timeout=5,
            )
        return self._api_client

    @property
    def cache(self) -> UtilizationCache:
        """Get or create the utilization cache."""
        if self._cache is None:
            self._cache = UtilizationCache(ttl=self.cache_ttl)
        return self._cache

    def set_router(self, router) -> None:
        """
        Set reference to the Router instance.

        This must be called after the Router is created to allow the custom
        routing strategy to access the Router's model_list.

        Args:
            router: The LiteLLM Router instance
        """
        self.router = router
        logger.info("Router reference set on ChutesUtilizationRouting")

    def _get_utilization(self, chute_id: str) -> Optional[float]:
        """
        Fetch utilization from Chutes API or return cached value.

        Args:
            chute_id: The Chutes deployment ID to check

        Returns:
            Utilization value (0.0 = idle, 1.0 = fully utilized), or None if unavailable
        """
        # Check cache first
        cached = self.cache.get(chute_id)
        if cached is not None:
            return cached

        # Fetch from API if not cached
        try:
            utilization = self.api_client.get_utilization(chute_id)

            if utilization is not None:
                self.cache.set(chute_id, utilization)
                logger.info(
                    f"Fetched and cached utilization for {chute_id}: {utilization}"
                )

            return utilization

        except Exception as e:
            logger.error(f"Error fetching utilization for {chute_id}: {e}")
            return None

    def _get_all_utilizations(
        self, model_list: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        """
        Get utilization for all available deployments.

        Args:
            model_list: List of model configurations from router

        Returns:
            Dictionary mapping chute_id to utilization value
        """
        utilizations: Dict[str, float] = {}

        for model_config in model_list:
            # Get chute_id from model_info
            # Priority: id (actual chute UUID from API) > chute_id (custom name)
            model_info = model_config.get("model_info", {})
            chute_id = model_info.get("id") or model_info.get("chute_id")

            if not chute_id:
                # Try to get from litellm_params or model name
                litellm_params = model_config.get("litellm_params", {})
                model = litellm_params.get("model", "")
                # Extract chute_id from model if possible
                if model:
                    chute_id = model.split("/")[-1]  # Get last part of "org/model"

            if chute_id:
                logger.debug(f"Fetching utilization for chute: {chute_id}")
                util = self._get_utilization(chute_id)
                if util is not None:
                    utilizations[chute_id] = util
                else:
                    # Use default (mid-range) if unavailable
                    utilizations[chute_id] = 0.5
                    logger.warning(
                        f"Could not get utilization for {chute_id}, using default 0.5"
                    )

        return utilizations

    def _find_least_utilized(self, utilizations: Dict[str, float]) -> Optional[str]:
        """
        Find the chute with lowest utilization.

        Args:
            utilizations: Dictionary mapping chute_id to utilization

        Returns:
            Chute ID with lowest utilization, or None if empty
        """
        if not utilizations:
            return None

        # Find key with minimum value
        return min(utilizations.items(), key=lambda x: x[1])[0]

    def _get_model_list(
        self, request_kwargs: Optional[Dict] = None
    ) -> List[Dict[str, Any]]:
        """
        Get the model list from various sources.

        Args:
            request_kwargs: Additional request parameters

        Returns:
            List of model configurations
        """
        model_list: List[Dict[str, Any]] = []

        # First, try to get model_list from the stored router reference
        if self.router is not None:
            model_list = getattr(self.router, "model_list", [])
            logger.debug(
                f"Got model_list from stored router: {len(model_list) if model_list else 0} items"
            )

        # Fallback: try getattr on self (for compatibility with older LiteLLM versions)
        if not model_list:
            model_list = getattr(self, "model_list", [])
            logger.debug(
                f"Got model_list via getattr on self: {len(model_list) if model_list else 0} items"
            )

        # Fallback to request_kwargs if available (for compatibility)
        if not model_list and request_kwargs and "router" in request_kwargs:
            router = request_kwargs["router"]
            model_list = router.model_list if hasattr(router, "model_list") else []
            logger.debug(
                f"Got model_list via request_kwargs: {len(model_list) if model_list else 0} items"
            )

        return model_list

    async def async_get_available_deployment(  # type: ignore[override]
        self,
        model: str,
        messages: Optional[List[Dict[str, str]]] = None,
        input: Optional[Union[str, List]] = None,
        specific_deployment: Optional[bool] = False,
        request_kwargs: Optional[Dict] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Asynchronously get the available deployment with lowest utilization.

        This method is called for each request to determine which deployment
        should handle the request. It uses the Chutes API to get real-time
        utilization data and routes to the least utilized deployment.

        Args:
            model: The model name being requested
            messages: Chat messages (if applicable)
            input: Input data for embeddings (if applicable)
            specific_deployment: Whether a specific deployment was requested
            request_kwargs: Additional request parameters

        Returns:
            Model configuration dict from model_list, or None to fall back to default
        """
        try:
            model_list = self._get_model_list(request_kwargs)

            if not model_list:
                logger.warning("No model list available for routing")
                return None

            # Get utilizations for all deployments
            utilizations = self._get_all_utilizations(model_list)

            if not utilizations:
                logger.warning("No utilization data available, falling back to default")
                return None

            # Find least utilized deployment
            least_utilized_chute = self._find_least_utilized(utilizations)

            if not least_utilized_chute:
                logger.warning("Could not determine least utilized deployment")
                return None

            logger.info(
                f"Routing to least utilized deployment: {least_utilized_chute} "
                f"(utilization: {utilizations[least_utilized_chute]:.2f})"
            )

            # Find the model config with this chute_id (check both id and chute_id)
            for model_config in model_list:
                model_info = model_config.get("model_info", {})
                # Check both 'id' (actual chute UUID) and 'chute_id' (custom name)
                chute_id_candidate = model_info.get("id") or model_info.get("chute_id")

                if chute_id_candidate == least_utilized_chute:
                    logger.info(
                        f"Selected deployment: {model_config.get('model_name')} "
                        f"(chute_id: {chute_id_candidate})"
                    )
                    return model_config

            # If no match by chute_id, return first matching model
            for model_config in model_list:
                if model_config.get("model_name") == model:
                    return model_config

            # Fallback: return first available
            return model_list[0] if model_list else None

        except Exception as e:
            logger.error(f"Error in async_get_available_deployment: {e}")
            return None

    def get_available_deployment(  # type: ignore[override]
        self,
        model: str,
        messages: Optional[List[Dict[str, str]]] = None,
        input: Optional[Union[str, List]] = None,
        specific_deployment: Optional[bool] = False,
        request_kwargs: Optional[Dict] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Synchronously get the available deployment with lowest utilization.

        This is the synchronous version of async_get_available_deployment.

        Args:
            model: The model name being requested
            messages: Chat messages (if applicable)
            input: Input data for embeddings (if applicable)
            specific_deployment: Whether a specific deployment was requested
            request_kwargs: Additional request parameters

        Returns:
            Model configuration dict from model_list, or None to fall back to default
        """
        try:
            model_list = self._get_model_list(request_kwargs)

            if not model_list:
                logger.warning("No model list available for routing")
                return None

            # Get utilizations for all deployments
            utilizations = self._get_all_utilizations(model_list)

            if not utilizations:
                logger.warning("No utilization data available, falling back to default")
                return None

            # Find least utilized deployment
            least_utilized_chute = self._find_least_utilized(utilizations)

            if not least_utilized_chute:
                logger.warning("Could not determine least utilized deployment")
                return None

            logger.info(
                f"Routing to least utilized deployment: {least_utilized_chute} "
                f"(utilization: {utilizations[least_utilized_chute]:.2f})"
            )

            # Find the model config with this chute_id (check both id and chute_id)
            for model_config in model_list:
                model_info = model_config.get("model_info", {})
                # Check both 'id' (actual chute UUID) and 'chute_id' (custom name)
                chute_id_candidate = model_info.get("id") or model_info.get("chute_id")

                if chute_id_candidate == least_utilized_chute:
                    logger.info(
                        f"Selected deployment: {model_config.get('model_name')} "
                        f"(chute_id: {chute_id_candidate})"
                    )
                    return model_config

            # If no match by chute_id, return first matching model
            for model_config in model_list:
                if model_config.get("model_name") == model:
                    return model_config

            # Fallback: return first available
            return model_list[0] if model_list else None

        except Exception as e:
            logger.error(f"Error in get_available_deployment: {e}")
            return None


def create_chutes_routing_strategy(
    chutes_api_key: Optional[str] = None, cache_ttl: int = 30
) -> ChutesUtilizationRouting:
    """
    Factory function to create a Chutes utilization routing strategy.

    Args:
        chutes_api_key: Optional API key override
        cache_ttl: Cache time-to-live in seconds

    Returns:
        Configured ChutesUtilizationRouting instance
    """
    return ChutesUtilizationRouting(chutes_api_key=chutes_api_key, cache_ttl=cache_ttl)


# ============================================================
# Intelligent Multi-Metric Routing - Strategy Types
# ============================================================

import os
from enum import Enum
from dataclasses import dataclass


class RoutingStrategy(Enum):
    """
    Available routing strategies for intelligent multi-metric routing.

    Each strategy uses different weights for the performance metrics:
    - SPEED: Prioritizes TPS (throughput)
    - LATENCY: Prioritizes TTFT (time to first token)
    - BALANCED: Equal weights (default)
    - QUALITY: Prioritizes reliability/quality
    - UTILIZATION_ONLY: Fallback mode, only uses utilization
    """

    SPEED = "speed"
    LATENCY = "latency"
    BALANCED = "balanced"
    QUALITY = "quality"
    UTILIZATION_ONLY = "utilization_only"

    @classmethod
    def from_string(cls, value: str) -> "RoutingStrategy":
        """Create enum from string value."""
        value_lower = value.lower().strip()
        for strategy in cls:
            if strategy.value == value_lower:
                return strategy
        return cls.BALANCED


# Predefined strategy weights
_DEFAULT_WEIGHTS = {
    RoutingStrategy.SPEED: None,  # type: ignore[assignment]
    RoutingStrategy.LATENCY: None,  # type: ignore[assignment]
    RoutingStrategy.BALANCED: None,  # type: ignore[assignment]
    RoutingStrategy.QUALITY: None,  # type: ignore[assignment]
    RoutingStrategy.UTILIZATION_ONLY: None,  # type: ignore[assignment]
}


def _init_default_weights() -> None:
    """Initialize default weights."""
    global _DEFAULT_WEIGHTS
    _DEFAULT_WEIGHTS[RoutingStrategy.SPEED] = StrategyWeights(
        tps=0.5, ttft=0.3, quality=0.1, utilization=0.1
    )
    _DEFAULT_WEIGHTS[RoutingStrategy.LATENCY] = StrategyWeights(
        tps=0.1, ttft=0.6, quality=0.15, utilization=0.15
    )
    _DEFAULT_WEIGHTS[RoutingStrategy.BALANCED] = StrategyWeights(
        tps=0.25, ttft=0.25, quality=0.25, utilization=0.25
    )
    _DEFAULT_WEIGHTS[RoutingStrategy.QUALITY] = StrategyWeights(
        tps=0.15, ttft=0.15, quality=0.5, utilization=0.2
    )
    _DEFAULT_WEIGHTS[RoutingStrategy.UTILIZATION_ONLY] = StrategyWeights(
        tps=0.0, ttft=0.0, quality=0.0, utilization=1.0
    )


@dataclass
class StrategyWeights:
    """
    Weight configuration for scoring.

    Weights determine how much each metric contributes to the final score.
    All weights should sum to 1.0.

    Attributes:
        tps: Weight for TPS (tokens per second)
        ttft: Weight for TTFT (time to first token)
        quality: Weight for quality (derived from total_invocations)
        utilization: Weight for utilization (lower is better)
    """

    tps: float = 0.25
    ttft: float = 0.25
    quality: float = 0.25
    utilization: float = 0.25

    @classmethod
    def from_strategy(cls, strategy: RoutingStrategy) -> "StrategyWeights":
        """Get default weights for a routing strategy."""
        if _DEFAULT_WEIGHTS.get(RoutingStrategy.SPEED) is None:
            _init_default_weights()
        return _DEFAULT_WEIGHTS.get(strategy, cls())

    @classmethod
    def from_env(cls) -> "StrategyWeights":
        """Create weights from environment variables."""

        def get_float(env_var: str, default: float) -> float:
            value = os.environ.get(env_var)
            if value is not None:
                try:
                    return float(value)
                except ValueError:
                    pass
            return default

        return cls(
            tps=get_float("ROUTING_TPS_WEIGHT", 0.25),
            ttft=get_float("ROUTING_TTFT_WEIGHT", 0.25),
            quality=get_float("ROUTING_QUALITY_WEIGHT", 0.25),
            utilization=get_float("ROUTING_UTILIZATION_WEIGHT", 0.25),
        )

    def validate(self) -> bool:
        """Validate that weights sum to 1.0."""
        total = self.tps + self.ttft + self.quality + self.utilization
        return abs(total - 1.0) < 0.001

    def to_dict(self) -> dict:
        """Convert to dictionary representation."""
        return {
            "tps": self.tps,
            "ttft": self.ttft,
            "quality": self.quality,
            "utilization": self.utilization,
        }


# Initialize default weights
_init_default_weights()
