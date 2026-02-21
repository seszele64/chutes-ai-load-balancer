"""
Custom Routing Strategy for LiteLLM using Chutes Utilization API.

This module implements a custom routing strategy that routes requests to the
least utilized Chutes deployment based on real-time utilization data from the
Chutes API.
"""

import os
import time
import logging
from typing import Optional, Union, List, Dict, Any, Tuple
from dataclasses import dataclass
import asyncio

import requests

from litellm import CustomRoutingStrategyBase


# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Represents a cached utilization value with timestamp."""

    utilization: float
    timestamp: float


class ChutesUtilizationRouting(CustomRoutingStrategyBase):
    """
    Custom routing strategy that routes requests to the least utilized
    Chutes deployment based on real-time utilization data.

    This strategy:
    1. Fetches utilization data from Chutes API for each deployment
    2. Caches the utilization data with configurable TTL
    3. Routes requests to the deployment with the lowest utilization
    4. Falls back to default behavior if API is unavailable
    """

    def __init__(
        self,
        chutes_api_key: Optional[str] = None,
        cache_ttl: int = 30,
        chutes_api_base: str = "https://api.chutes.ai",
    ):
        """
        Initialize the Chutes utilization routing strategy.

        Args:
            chutes_api_key: API key for Chutes API. Falls back to CHUTES_API_KEY env var.
            cache_ttl: Time-to-live for cache entries in seconds (default: 30)
            chutes_api_base: Base URL for Chutes API (default: https://api.chutes.ai)
        """
        self.chutes_api_key = chutes_api_key or os.environ.get("CHUTES_API_KEY")
        self.cache_ttl = cache_ttl
        self.chutes_api_base = chutes_api_base
        self.router = None  # Reference to the Router instance, set via set_router()

        # Cache: {chute_id: CacheEntry}
        self.utilization_cache: Dict[str, CacheEntry] = {}

        logger.info(
            f"ChutesUtilizationRouting initialized with cache_ttl={cache_ttl}s, "
            f"api_base={chutes_api_base}"
        )

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

    def _get_cached_utilization(self, chute_id: str) -> Optional[float]:
        """
        Get cached utilization value if still valid.

        Args:
            chute_id: The Chutes deployment ID

        Returns:
            Cached utilization value or None if expired/not cached
        """
        if chute_id not in self.utilization_cache:
            return None

        entry = self.utilization_cache[chute_id]
        age = time.time() - entry.timestamp

        if age > self.cache_ttl:
            logger.debug(f"Cache expired for {chute_id}, age={age:.1f}s")
            del self.utilization_cache[chute_id]
            return None

        logger.debug(
            f"Cache hit for {chute_id}, age={age:.1f}s, util={entry.utilization}"
        )
        return entry.utilization

    def _set_cached_utilization(self, chute_id: str, utilization: float) -> None:
        """
        Store utilization value in cache.

        Args:
            chute_id: The Chutes deployment ID
            utilization: The utilization value (0.0 to 1.0)
        """
        self.utilization_cache[chute_id] = CacheEntry(
            utilization=utilization, timestamp=time.time()
        )
        logger.debug(f"Cached utilization for {chute_id}: {utilization}")

    def _get_utilization(self, chute_id: str) -> Optional[float]:
        """
        Fetch utilization from Chutes API or return cached value.

        Args:
            chute_id: The Chutes deployment ID to check

        Returns:
            Utilization value (0.0 = idle, 1.0 = fully utilized), or None if unavailable
        """
        # Check cache first
        cached = self._get_cached_utilization(chute_id)
        if cached is not None:
            return cached

        # Fetch from API if not cached
        if not self.chutes_api_key:
            logger.warning(f"No Chutes API key available for chute {chute_id}")
            return None

        try:
            url = f"{self.chutes_api_base}/chutes/utilization"
            headers = {
                "X-API-Key": self.chutes_api_key,
                "Content-Type": "application/json",
            }

            logger.debug(f"Fetching utilization for {chute_id} from {url}")
            response = requests.get(
                url,
                headers=headers,
                timeout=5,  # 5 second timeout
            )
            response.raise_for_status()

            data = response.json()

            # Parse utilization from response
            # The API returns utilization data - adjust based on actual API response format
            utilization = self._parse_utilization_response(data, chute_id)

            if utilization is not None:
                self._set_cached_utilization(chute_id, utilization)
                logger.info(f"Fetched utilization for {chute_id}: {utilization}")

            return utilization

        except requests.exceptions.Timeout:
            logger.error(f"Timeout fetching utilization for {chute_id}")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching utilization for {chute_id}: {e}")
            return None
        except (KeyError, ValueError) as e:
            logger.error(f"Error parsing utilization response for {chute_id}: {e}")
            return None

    def _parse_utilization_response(
        self, data: Dict[str, Any], chute_id: str
    ) -> Optional[float]:
        """
        Parse utilization from API response.

        The API returns a list of chute utilization objects:
        [
            {
                "chute_id": "uuid...",
                "name": "model/name",
                "timestamp": "...",
                "utilization_current": 0.5,
                "utilization_5m": 0.4,
                ...
            },
            ...
        ]

        Args:
            data: API response data (list or dict)
            chute_id: The chute ID being queried

        Returns:
            Utilization value (0.0 to 1.0) or None if not found
        """
        # Handle list response format (actual Chutes API format)
        if isinstance(data, list):
            # Try to find matching chute by chute_id first
            for item in data:
                if item.get("chute_id") == chute_id:
                    # Use current utilization (most real-time)
                    util = item.get("utilization_current")
                    if util is not None:
                        return float(util)
                    # Fallback to 5m average
                    util = item.get("utilization_5m")
                    if util is not None:
                        return float(util)
                    # Fallback to 15m average
                    util = item.get("utilization_15m")
                    if util is not None:
                        return float(util)

            # If not found by chute_id, try to match by name/model
            # Extract model name from the chute_id if it's a custom ID
            for item in data:
                name = item.get("name", "")
                # Check if the chute_id matches any part of the name
                # e.g., "chute_kimi_k2.5_tee" should match "moonshotai/Kimi-K2.5-TEE"
                chute_id_normalized = (
                    chute_id.replace("chute_", "").replace("_", "-").lower()
                )
                name_normalized = name.replace("/", " ").replace("-", " ").lower()
                if (
                    chute_id_normalized in name_normalized
                    or name_normalized in chute_id_normalized
                ):
                    util = item.get("utilization_current")
                    if util is not None:
                        return float(util)

            logger.warning(f"Could not find chute {chute_id} in utilization response")
            return None

        # Handle dict response format (legacy/alternative format)
        if isinstance(data, dict):
            # Try common field names
            for field in ["utilization", "util", "usage", "load", "capacity"]:
                if field in data:
                    value = data[field]
                    if isinstance(value, (int, float)):
                        return float(value)

            # Format 2: Per-chute data
            if "chutes" in data and isinstance(data["chutes"], dict):
                chute_data = data["chutes"].get(chute_id, {})
                for field in ["utilization", "util", "usage", "load"]:
                    if field in chute_data:
                        return float(chute_data[field])

                # Try getting from the first available chute
                if not chute_data:
                    for cid, cdata in data["chutes"].items():
                        for field in ["utilization", "util", "usage", "load"]:
                            if field in cdata:
                                return float(cdata[field])

            # Format 3: Array of chute data
            if isinstance(data.get("data"), list):
                for item in data["data"]:
                    if item.get("chute_id") == chute_id or item.get("id") == chute_id:
                        for field in ["utilization", "util", "usage", "load"]:
                            if field in item:
                                return float(item[field])

        logger.warning(f"Could not parse utilization from response: {data}")
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
        utilizations = {}

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

    # Type ignore comments needed because base class lacks proper type hints
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
            # First, try to get model_list from the stored router reference
            model_list = []

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
            # First, try to get model_list from the stored router reference
            model_list = []

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
