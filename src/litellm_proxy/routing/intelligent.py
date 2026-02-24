"""
Intelligent Multi-Metric Routing Strategy.

This module provides the main routing strategy that considers multiple
performance metrics (TPS, TTFT, quality, utilization) for optimal
request distribution across AI model deployments.
"""

import logging
import math
import random
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List, Union

from litellm import CustomRoutingStrategyBase

from litellm_proxy.routing.metrics import ChuteMetrics, ChuteScore, RoutingDecision
from litellm_proxy.routing.strategy import RoutingStrategy, StrategyWeights
from litellm_proxy.routing.cache import MetricsCache
from litellm_proxy.api.client import ChutesAPIClient
from litellm_proxy.exceptions import ChutesRoutingError

logger = logging.getLogger(__name__)


class ChutesRoutingStrategy(ABC):
    """Abstract base class for routing strategies."""

    @abstractmethod
    def select_chute(
        self, chutes: List[ChuteMetrics], weights: Optional[StrategyWeights] = None
    ) -> RoutingDecision:
        """Select the best chute based on metrics and weights."""
        pass


class IntelligentMultiMetricRouting(ChutesRoutingStrategy, CustomRoutingStrategyBase):
    """
    Multi-metric routing strategy that considers:
    - TPS (tokens per second)
    - TTFT (time to first token)
    - Quality (derived from total_invocations)
    - Utilization (current load)

    Uses Strategy pattern for pluggable scoring algorithms.
    Coexists with existing ChutesUtilizationRouting.
    """

    # High utilization threshold for warnings
    HIGH_UTILIZATION_THRESHOLD = 0.8

    def __init__(
        self,
        strategy: RoutingStrategy = RoutingStrategy.BALANCED,
        custom_weights: Optional[StrategyWeights] = None,
        cache: Optional[MetricsCache] = None,
        api_client: Optional[ChutesAPIClient] = None,
        chutes_api_key: Optional[str] = None,
        chutes_api_base: str = "https://api.chutes.ai",
        cache_ttl_utilization: int = 30,
        cache_ttl_tps: int = 300,
        cache_ttl_ttft: int = 300,
        cache_ttl_quality: int = 300,
    ):
        """
        Initialize the intelligent multi-metric routing strategy.

        Args:
            strategy: The routing strategy to use
            custom_weights: Optional custom weights (overrides strategy defaults)
            cache: Optional MetricsCache instance
            api_client: Optional ChutesAPIClient instance
            chutes_api_key: API key for Chutes API
            chutes_api_base: Base URL for Chutes API
            cache_ttl_utilization: Cache TTL for utilization (seconds)
            cache_ttl_tps: Cache TTL for TPS (seconds)
            cache_ttl_ttft: Cache TTL for TTFT (seconds)
            cache_ttl_quality: Cache TTL for quality (seconds)
        """
        self.strategy = strategy
        self.weights = custom_weights or StrategyWeights.from_strategy(strategy)
        self.chutes_api_key = chutes_api_key
        self.chutes_api_base = chutes_api_base

        # Validate weights
        if not self.weights.validate():
            raise ValueError("Weights must sum to 1.0")

        # Initialize cache with custom TTLs
        if cache is not None:
            self._cache = cache
        else:
            self._cache = MetricsCache(
                ttls={
                    "utilization": cache_ttl_utilization,
                    "tps": cache_ttl_tps,
                    "ttft": cache_ttl_ttft,
                    "quality": cache_ttl_quality,
                    "total_invocations": cache_ttl_quality,
                }
            )

        # Initialize API client
        self._api_client = api_client

        # Router reference (set via set_router)
        self.router = None

        logger.info(
            f"IntelligentMultiMetricRouting initialized with strategy={strategy.value}, "
            f"weights={self.weights.to_dict()}"
        )

    @property
    def cache(self) -> MetricsCache:
        """Get the metrics cache."""
        return self._cache

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

    def set_router(self, router) -> None:
        """Set reference to the Router instance."""
        self.router = router
        logger.info("Router reference set on IntelligentMultiMetricRouting")

    def select_chute(
        self, chutes: List[ChuteMetrics], weights: Optional[StrategyWeights] = None
    ) -> RoutingDecision:
        """Select best chute using multi-metric scoring."""

        # Use provided weights or fall back to strategy weights
        effective_weights = weights or self.weights

        # Edge case: single chute
        if len(chutes) == 1:
            return RoutingDecision(
                selected_chute=chutes[0].chute_id,
                decision_reason="Only one chute available",
                cache_hit=self.cache.is_warm(),
            )

        # Check if we have complete metrics for multi-metric scoring
        complete_metrics = [c for c in chutes if c.is_complete()]

        if not complete_metrics:
            # Fallback to utilization-only
            return self._fallback_to_utilization(chutes)

        # Calculate scores
        scores = self._calculate_scores(complete_metrics, effective_weights)

        # Select highest scoring chute
        selected = max(scores.items(), key=lambda x: x[1].total_score)

        # Check for high utilization warning
        warning = None
        if all(
            c.utilization and c.utilization > self.HIGH_UTILIZATION_THRESHOLD
            for c in chutes
        ):
            warning = f"All chutes above {self.HIGH_UTILIZATION_THRESHOLD * 100:.0f}% utilization"

        return RoutingDecision(
            selected_chute=selected[0],
            scores=scores,
            decision_reason=self._generate_reason(selected[1], chutes),
            cache_hit=self.cache.is_warm(),
            warning=warning,
        )

    def _calculate_scores(
        self, chutes: List[ChuteMetrics], weights: StrategyWeights
    ) -> Dict[str, ChuteScore]:
        """Calculate normalized scores for all chutes."""

        # Find min/max for normalization
        tps_values = [c.tps for c in chutes if c.tps is not None]
        ttft_values = [c.ttft for c in chutes if c.ttft is not None]
        quality_values = [
            self._derive_quality(c) for c in chutes if c.total_invocations is not None
        ]
        util_values = [c.utilization for c in chutes if c.utilization is not None]

        scores = {}
        for chute in chutes:
            score = ChuteScore(chute_id=chute.chute_id)

            # TPS: higher is better - use value/max scaling (ratio-based)
            if tps_values:
                tps_max = max(tps_values)
                if tps_max > 0 and chute.tps is not None:
                    score.tps_normalized = min(1.0, chute.tps / tps_max)
                else:
                    score.tps_normalized = 1.0
                score.raw_tps = chute.tps

            # TTFT: lower is better - use min/ttft ratio
            # This ensures higher score for lower TTFT
            if ttft_values:
                ttft_min = min(ttft_values)
                if ttft_min > 0 and chute.ttft is not None:
                    score.ttft_normalized = min(1.0, ttft_min / chute.ttft)
                else:
                    score.ttft_normalized = 1.0
                score.raw_ttft = chute.ttft

            # Quality: derived from total_invocations - use value/max ratio
            # Higher invocations = better quality
            if quality_values:
                q = self._derive_quality(chute)
                q_max = max(quality_values)
                if q_max > 0 and q > 0:
                    score.quality_normalized = min(1.0, q / q_max)
                else:
                    score.quality_normalized = 1.0
                score.raw_quality = q

            # Utilization: lower is better - use min/utilization ratio
            # Lower utilization = higher score
            if util_values:
                util_min = min(util_values)
                if (
                    util_min > 0
                    and chute.utilization is not None
                    and chute.utilization > 0
                ):
                    score.utilization_normalized = min(
                        1.0, util_min / chute.utilization
                    )
                else:
                    score.utilization_normalized = 1.0
                score.raw_utilization = chute.utilization

            # Weighted total
            score.total_score = (
                score.tps_normalized * weights.tps
                + score.ttft_normalized * weights.ttft
                + score.quality_normalized * weights.quality
                + score.utilization_normalized * weights.utilization
            )

            scores[chute.chute_id] = score

        return scores

    def _derive_quality(self, chute: ChuteMetrics) -> float:
        """Derive quality score from total_invocations (reliability proxy)."""
        if chute.total_invocations is None:
            return 0.0
        # Normalize to 0-1 based on log scale
        # 10^6 invocations = 1.0 quality
        if chute.total_invocations > 0:
            return min(1.0, math.log10(chute.total_invocations + 1) / 6.0)
        return 0.0

    def _fallback_to_utilization(self, chutes: List[ChuteMetrics]) -> RoutingDecision:
        """Fallback when TPS/TTFT unavailable."""
        if not all(c.utilization is not None for c in chutes):
            # No utilization data either - random selection
            return RoutingDecision(
                selected_chute=random.choice(chutes).chute_id,
                fallback_mode=True,
                decision_reason="No metrics available - random selection",
            )

        # Select lowest utilization
        selected = min(chutes, key=lambda c: c.utilization or float("inf"))
        return RoutingDecision(
            selected_chute=selected.chute_id,
            fallback_mode=True,
            decision_reason=f"Fallback to utilization-only: {selected.chute_id} ({selected.utilization:.2f})",
        )

    def _generate_reason(self, score: ChuteScore, chutes: List[ChuteMetrics]) -> str:
        """Generate human-readable decision reason."""
        chute = next((c for c in chutes if c.chute_id == score.chute_id), None)
        if not chute:
            return ""

        reasons = []

        # Identify winning metric
        max_score = max(
            score.tps_normalized,
            score.ttft_normalized,
            score.quality_normalized,
            score.utilization_normalized,
        )

        if score.tps_normalized >= max_score and chute.tps is not None:
            reasons.append(f"highest TPS ({chute.tps:.2f})")
        elif score.ttft_normalized >= max_score and chute.ttft is not None:
            reasons.append(f"lowest TTFT ({chute.ttft:.2f}s)")
        elif (
            score.quality_normalized >= max_score
            and chute.total_invocations is not None
        ):
            reasons.append(
                f"highest reliability ({chute.total_invocations} invocations)"
            )
        else:
            reasons.append(f"lowest utilization ({chute.utilization:.2f})")

        return f"{chute.chute_id} selected: {', '.join(reasons)}"

    # ============================================================
    # LiteLLM CustomRoutingStrategyBase methods
    # ============================================================

    def _get_model_list(
        self, request_kwargs: Optional[Dict] = None
    ) -> List[Dict[str, Any]]:
        """Get the model list from various sources."""
        model_list: List[Dict[str, Any]] = []

        if self.router is not None:
            model_list = getattr(self.router, "model_list", [])

        if not model_list:
            model_list = getattr(self, "model_list", [])

        if not model_list and request_kwargs and "router" in request_kwargs:
            router = request_kwargs["router"]
            model_list = router.model_list if hasattr(router, "model_list") else []

        return model_list

    def _get_chute_ids_from_model_list(
        self, model_list: List[Dict[str, Any]]
    ) -> Dict[str, Dict[str, str]]:
        """Extract chute IDs from model list."""
        chute_map = {}

        for model_config in model_list:
            model_info = model_config.get("model_info", {})
            chute_id = model_info.get("id") or model_info.get("chute_id")

            if not chute_id:
                litellm_params = model_config.get("litellm_params", {})
                model = litellm_params.get("model", "")
                if model:
                    chute_id = model.split("/")[-1]
            else:
                litellm_params = model_config.get("litellm_params", {})

            if chute_id:
                chute_map[chute_id] = {
                    "model_name": model_config.get("model_name", ""),
                    "model": litellm_params.get("model", ""),
                }

        return chute_map

    async def async_get_available_deployment(  # type: ignore[override]
        self,
        model: str,
        messages: Optional[List[Dict[str, str]]] = None,
        input: Optional[Union[str, List]] = None,
        specific_deployment: Optional[bool] = False,
        request_kwargs: Optional[Dict] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Asynchronously get the available deployment based on multi-metric routing.
        """
        try:
            model_list = self._get_model_list(request_kwargs)

            if not model_list:
                logger.warning("No model list available for routing")
                return None

            # Get chute IDs from model list
            chute_map = self._get_chute_ids_from_model_list(model_list)
            chute_ids = list(chute_map.keys())

            # Try to get from cache first
            cached_metrics = []
            for chute_id in chute_ids:
                cached = self.cache.get_all(chute_id)
                if cached:
                    cached_metrics.append(cached)

            # If we have some cached data, use it
            if cached_metrics:
                decision = self.select_chute(cached_metrics)
                return self._find_model_config_by_chute(
                    model_list, decision.selected_chute
                )

            # Fetch from API
            try:
                all_metrics = self.api_client.get_bulk_utilization()
                llm_stats = self.api_client.get_llm_stats()

                # Build ChuteMetrics for each chute
                chute_metrics = []
                for chute_id in chute_ids:
                    metrics = ChuteMetrics(
                        chute_id=chute_id,
                        model=chute_map[chute_id].get("model", ""),
                        utilization=all_metrics.get(chute_id),
                        tps=llm_stats.get(chute_id, {}).get("tps"),
                        ttft=llm_stats.get(chute_id, {}).get("ttft"),
                    )
                    chute_metrics.append(metrics)
                    # Cache the metrics
                    self.cache.set_all(metrics)

                if chute_metrics:
                    decision = self.select_chute(chute_metrics)
                    return self._find_model_config_by_chute(
                        model_list, decision.selected_chute
                    )

            except Exception as e:
                logger.warning(f"Error fetching metrics from API: {e}")
                # Fallback to existing ChutesUtilizationRouting behavior
                return None

            return None

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
        Synchronously get the available deployment based on multi-metric routing.
        """
        try:
            model_list = self._get_model_list(request_kwargs)

            if not model_list:
                logger.warning("No model list available for routing")
                return None

            chute_map = self._get_chute_ids_from_model_list(model_list)
            chute_ids = list(chute_map.keys())

            # Try to get from cache first
            cached_metrics = []
            for chute_id in chute_ids:
                cached = self.cache.get_all(chute_id)
                if cached:
                    cached_metrics.append(cached)

            if cached_metrics:
                decision = self.select_chute(cached_metrics)
                return self._find_model_config_by_chute(
                    model_list, decision.selected_chute
                )

            # Fetch from API
            try:
                all_metrics = self.api_client.get_bulk_utilization()
                llm_stats = self.api_client.get_llm_stats()

                chute_metrics = []
                for chute_id in chute_ids:
                    metrics = ChuteMetrics(
                        chute_id=chute_id,
                        model=chute_map[chute_id].get("model", ""),
                        utilization=all_metrics.get(chute_id),
                        tps=llm_stats.get(chute_id, {}).get("tps"),
                        ttft=llm_stats.get(chute_id, {}).get("ttft"),
                    )
                    chute_metrics.append(metrics)
                    self.cache.set_all(metrics)

                if chute_metrics:
                    decision = self.select_chute(chute_metrics)
                    return self._find_model_config_by_chute(
                        model_list, decision.selected_chute
                    )

            except Exception as e:
                logger.warning(f"Error fetching metrics from API: {e}")
                return None

            return None

        except Exception as e:
            logger.error(f"Error in get_available_deployment: {e}")
            return None

    def _find_model_config_by_chute(
        self, model_list: List[Dict[str, Any]], chute_id: str
    ) -> Optional[Dict[str, Any]]:
        """Find model config by chute ID."""
        for model_config in model_list:
            model_info = model_config.get("model_info", {})
            candidate = model_info.get("id") or model_info.get("chute_id")

            if candidate == chute_id:
                return model_config

        # Fallback to first matching model
        return model_list[0] if model_list else None


# Type alias for union
from typing import Union
