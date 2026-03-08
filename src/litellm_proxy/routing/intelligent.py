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
from litellm_proxy.routing.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
from litellm_proxy.routing.responses import ResponseBuilder, DegradationLevel
from litellm_proxy.api.client import ChutesAPIClient
from litellm_proxy.exceptions import (
    ChutesRoutingError,
    EmptyModelListError,
    DegradationExhaustedError,
)

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
        enable_circuit_breaker: Optional[bool] = None,
        enable_degradation: Optional[bool] = None,
        circuit_breaker_failure_threshold: Optional[int] = None,
        circuit_breaker_timeout_seconds: Optional[int] = None,
        cache_ttl_seconds: Optional[int] = None,
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
            enable_circuit_breaker: Enable circuit breaker for API calls (default: True)
            enable_degradation: Enable graceful degradation (default: True)
            circuit_breaker_failure_threshold: Failure threshold for circuit breaker
            circuit_breaker_timeout_seconds: Timeout in seconds for circuit breaker
            cache_ttl_seconds: Default cache TTL for all metrics
        """
        import os

        # Read from environment variables if not provided explicitly
        # USE_STRUCTURED_RESPONSES (legacy, maps to enable_degradation)
        use_structured = os.environ.get("USE_STRUCTURED_RESPONSES")
        if use_structured is not None and enable_degradation is None:
            enable_degradation = use_structured.lower() in ("true", "1", "yes")

        # CIRCUIT_BREAKER_ENABLED
        if enable_circuit_breaker is None:
            cb_enabled = os.environ.get("CIRCUIT_BREAKER_ENABLED")
            enable_circuit_breaker = cb_enabled is None or cb_enabled.lower() in (
                "true",
                "1",
                "yes",
            )

        # CIRCUIT_BREAKER_FAILURE_THRESHOLD
        if circuit_breaker_failure_threshold is None:
            cb_threshold = os.environ.get("CIRCUIT_BREAKER_FAILURE_THRESHOLD")
            if cb_threshold is not None:
                circuit_breaker_failure_threshold = int(cb_threshold)

        # CIRCUIT_BREAKER_TIMEOUT_SECONDS
        if circuit_breaker_timeout_seconds is None:
            cb_timeout = os.environ.get("CIRCUIT_BREAKER_TIMEOUT_SECONDS")
            if cb_timeout is not None:
                circuit_breaker_timeout_seconds = int(cb_timeout)

        # CACHE_TTL_SECONDS
        if cache_ttl_seconds is not None:
            cache_ttl_utilization = cache_ttl_seconds

        # DEGRADATION_ENABLED
        if enable_degradation is None:
            deg_enabled = os.environ.get("DEGRADATION_ENABLED")
            enable_degradation = deg_enabled is None or deg_enabled.lower() in (
                "true",
                "1",
                "yes",
            )

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

        # Initialize circuit breaker with optional configuration
        if enable_circuit_breaker:
            cb_config = None
            if (
                circuit_breaker_failure_threshold is not None
                or circuit_breaker_timeout_seconds is not None
            ):
                from litellm_proxy.routing.circuit_breaker import CircuitBreakerConfig

                cb_config = CircuitBreakerConfig(
                    failure_threshold=circuit_breaker_failure_threshold or 3,
                    cooldown_seconds=circuit_breaker_timeout_seconds or 30,
                )
            self._circuit_breaker = (
                CircuitBreaker(cb_config) if enable_circuit_breaker else None
            )
        else:
            self._circuit_breaker = None

        # Initialize response builder
        self._response_builder = ResponseBuilder()

        # Feature flags for degradation
        self._enable_degradation = enable_degradation

        # Router reference (set via set_router)
        self.router = None

        logger.info(
            f"IntelligentMultiMetricRouting initialized with strategy={strategy.value}, "
            f"weights={self.weights.to_dict()}, "
            f"circuit_breaker={enable_circuit_breaker}, "
            f"degradation={enable_degradation}"
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

    @property
    def circuit_breaker_status(self) -> Optional[dict]:
        """Get circuit breaker status for debugging."""
        if self._circuit_breaker:
            return self._circuit_breaker.get_status()
        return None

    @property
    def is_circuit_breaker_open(self) -> bool:
        """Check if circuit breaker is open."""
        if self._circuit_breaker:
            return self._circuit_breaker.is_open()
        return False

    def get_health_status(self) -> dict:
        """
        Get health status of the routing subsystem.

        Returns:
            Dict with health information including:
            - status: "healthy", "degraded", or "unhealthy"
            - circuit_breaker_state: Current state
            - last_successful_request: Timestamp
            - consecutive_failures: Current failure count
            - degradation_level: Current system degradation
        """
        status = "healthy"
        degradation_level = 0

        if self._circuit_breaker:
            cb_status = self._circuit_breaker.get_status()
            cb_state = cb_status.get("state", "unknown")

            if cb_state == "open":
                status = "unhealthy"
                degradation_level = 4
            elif cb_state == "half_open":
                status = "degraded"
                degradation_level = 3
            elif cb_status.get("failure_count", 0) > 0:
                status = "degraded"
                degradation_level = 1

        # Check cache health
        if not self.cache.is_warm():
            if status == "healthy":
                status = "degraded"
            degradation_level = max(degradation_level, 1)

        return {
            "status": status,
            "circuit_breaker_state": (
                self._circuit_breaker.get_status().get("state", "disabled")
                if self._circuit_breaker
                else "disabled"
            ),
            "last_successful_request": (
                self._circuit_breaker.get_status().get("last_success_time")
                if self._circuit_breaker
                else None
            ),
            "consecutive_failures": (
                self._circuit_breaker.get_status().get("failure_count", 0)
                if self._circuit_breaker
                else 0
            ),
            "degradation_level": degradation_level,
            "cache_warm": self.cache.is_warm(),
        }

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
    ) -> Dict[str, Any]:
        """
        Asynchronously get the available deployment based on multi-metric routing.

        Returns deployment dict with routing metadata, or raises exception on failure.
        """
        try:
            model_list = self._get_model_list(request_kwargs)

            if not model_list:
                logger.warning("No model list available for routing")
                raise EmptyModelListError("No model list available for routing")

            # Get chute IDs from model list
            chute_map = self._get_chute_ids_from_model_list(model_list)
            chute_ids = list(chute_map.keys())

            # Check circuit breaker before making API calls
            if self._circuit_breaker and self._circuit_breaker.is_open():
                logger.warning(
                    f"Circuit breaker open, using degraded response. "
                    f"Cooldown remaining: {self._circuit_breaker.get_cooldown_remaining():.1f}s"
                )
                return self._degrade_to_fallback(
                    model_list, chute_ids, DegradationLevel.CACHED
                )

            # Try to get from cache first (Level 1: Cached)
            cached_metrics = []
            for chute_id in chute_ids:
                cached = self.cache.get_all(chute_id)
                if cached:
                    cached_metrics.append(cached)

            # If we have some cached data, use it
            if cached_metrics:
                logger.info("Using cached metrics for routing (degradation level 1)")
                decision = self.select_chute(cached_metrics)
                deployment = self._find_model_config_by_chute(
                    model_list, decision.selected_chute
                )
                if deployment:
                    return self._response_builder.build_success(
                        deployment, DegradationLevel.CACHED
                    )

            # Fetch from API (Level 0: Full metrics)
            try:
                all_metrics = self.api_client.get_bulk_utilization()
                llm_stats = self.api_client.get_llm_stats()

                # Record success if circuit breaker is enabled
                if self._circuit_breaker:
                    self._circuit_breaker.record_success()

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
                    deployment = self._find_model_config_by_chute(
                        model_list, decision.selected_chute
                    )
                    if deployment:
                        return self._response_builder.build_success(
                            deployment, DegradationLevel.FULL
                        )

            except Exception as e:
                logger.warning(f"Error fetching metrics from API: {e}")
                # Record failure in circuit breaker
                if self._circuit_breaker:
                    self._circuit_breaker.record_failure()

                # Try degradation (Level 2: Utilization-only)
                if self._enable_degradation:
                    return self._degrade_to_utilization(
                        model_list, chute_map, chute_ids
                    )

            # If no metrics at all, try degradation (Level 3: Random)
            if self._enable_degradation:
                return self._degrade_to_random(model_list, chute_ids)

            # Complete failure - raise exception (Level 4)
            raise DegradationExhaustedError(
                levels_attempted=["full", "cached", "utilization", "random"],
                original_error=None,
            )

        except DegradationExhaustedError:
            raise
        except EmptyModelListError:
            raise
        except Exception as e:
            logger.error(f"Error in async_get_available_deployment: {e}")
            raise DegradationExhaustedError(levels_attempted=["full"], original_error=e)

    def _degrade_to_fallback(
        self,
        model_list: List[Dict[str, Any]],
        chute_ids: List[str],
        level: int,
    ) -> Dict[str, Any]:
        """Return degraded response when circuit breaker is open."""
        # Try cached metrics first
        cached_metrics = []
        for chute_id in chute_ids:
            cached = self.cache.get_all(chute_id)
            if cached:
                cached_metrics.append(cached)

        if cached_metrics:
            logger.info("Using cached metrics for degraded response")
            decision = self.select_chute(cached_metrics)
            deployment = self._find_model_config_by_chute(
                model_list, decision.selected_chute
            )
            if deployment:
                return self._response_builder.build_success(deployment, level)

        # Fall back to random selection
        return self._degrade_to_random(model_list, chute_ids)

    def _degrade_to_utilization(
        self,
        model_list: List[Dict[str, Any]],
        chute_map: Dict[str, Any],
        chute_ids: List[str],
    ) -> Dict[str, Any]:
        """Try utilization-only routing as degradation level 2."""
        logger.warning("Attempting utilization-only routing (degradation level 2)")

        try:
            # Try to get just utilization data
            utilization_data = {}
            for chute_id in chute_ids:
                try:
                    util = self.api_client.get_utilization(chute_id)
                    if util is not None:
                        utilization_data[chute_id] = util
                except Exception as e:
                    logger.debug(f"Failed to get utilization for {chute_id}: {e}")

            if utilization_data:
                # Build metrics with just utilization
                chute_metrics = []
                for chute_id in chute_ids:
                    metrics = ChuteMetrics(
                        chute_id=chute_id,
                        model=chute_map.get(chute_id, {}).get("model", ""),
                        utilization=utilization_data.get(chute_id),
                        tps=None,
                        ttft=None,
                    )
                    chute_metrics.append(metrics)

                # Use fallback selection
                decision = self._fallback_to_utilization(chute_metrics)
                deployment = self._find_model_config_by_chute(
                    model_list, decision.selected_chute
                )
                if deployment:
                    return self._response_builder.build_success(
                        deployment, DegradationLevel.UTILIZATION
                    )

        except Exception as e:
            logger.warning(f"Utilization-only routing failed: {e}")

        # Fall through to random selection
        return self._degrade_to_random(model_list, chute_ids)

    def _degrade_to_random(
        self,
        model_list: List[Dict[str, Any]],
        chute_ids: List[str],
    ) -> Dict[str, Any]:
        """Random selection as last resort (degradation level 3)."""
        if not chute_ids:
            raise DegradationExhaustedError(
                levels_attempted=["full", "cached", "utilization", "random"],
                original_error=None,
            )

        logger.error(
            f"No metrics available, performing random selection from {len(chute_ids)} chutes"
        )
        selected_chute = random.choice(chute_ids)
        deployment = self._find_model_config_by_chute(model_list, selected_chute)

        if deployment:
            return self._response_builder.build_success(
                deployment, DegradationLevel.RANDOM
            )

        raise DegradationExhaustedError(
            levels_attempted=["full", "cached", "utilization", "random"],
            original_error=None,
        )

    def get_available_deployment(  # type: ignore[override]
        self,
        model: str,
        messages: Optional[List[Dict[str, str]]] = None,
        input: Optional[Union[str, List]] = None,
        specific_deployment: Optional[bool] = False,
        request_kwargs: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Synchronously get the available deployment based on multi-metric routing.

        Returns deployment dict with routing metadata, or raises exception on failure.
        """
        try:
            model_list = self._get_model_list(request_kwargs)

            if not model_list:
                logger.warning("No model list available for routing")
                raise EmptyModelListError("No model list available for routing")

            chute_map = self._get_chute_ids_from_model_list(model_list)
            chute_ids = list(chute_map.keys())

            # Check circuit breaker before making API calls
            if self._circuit_breaker and self._circuit_breaker.is_open():
                logger.warning(
                    f"Circuit breaker open, using degraded response. "
                    f"Cooldown remaining: {self._circuit_breaker.get_cooldown_remaining():.1f}s"
                )
                return self._degrade_to_fallback(
                    model_list, chute_ids, DegradationLevel.CACHED
                )

            # Try to get from cache first (Level 1: Cached)
            cached_metrics = []
            for chute_id in chute_ids:
                cached = self.cache.get_all(chute_id)
                if cached:
                    cached_metrics.append(cached)

            if cached_metrics:
                logger.info("Using cached metrics for routing (degradation level 1)")
                decision = self.select_chute(cached_metrics)
                deployment = self._find_model_config_by_chute(
                    model_list, decision.selected_chute
                )
                if deployment:
                    return self._response_builder.build_success(
                        deployment, DegradationLevel.CACHED
                    )

            # Fetch from API (Level 0: Full metrics)
            try:
                all_metrics = self.api_client.get_bulk_utilization()
                llm_stats = self.api_client.get_llm_stats()

                # Record success if circuit breaker is enabled
                if self._circuit_breaker:
                    self._circuit_breaker.record_success()

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
                    deployment = self._find_model_config_by_chute(
                        model_list, decision.selected_chute
                    )
                    if deployment:
                        return self._response_builder.build_success(
                            deployment, DegradationLevel.FULL
                        )

            except Exception as e:
                logger.warning(f"Error fetching metrics from API: {e}")
                # Record failure in circuit breaker
                if self._circuit_breaker:
                    self._circuit_breaker.record_failure()

                # Try degradation (Level 2: Utilization-only)
                if self._enable_degradation:
                    return self._degrade_to_utilization(
                        model_list, chute_map, chute_ids
                    )

            # If no metrics at all, try degradation (Level 3: Random)
            if self._enable_degradation:
                return self._degrade_to_random(model_list, chute_ids)

            # Complete failure - raise exception (Level 4)
            raise DegradationExhaustedError(
                levels_attempted=["full", "cached", "utilization", "random"],
                original_error=None,
            )

        except DegradationExhaustedError:
            raise
        except EmptyModelListError:
            raise
        except Exception as e:
            logger.error(f"Error in get_available_deployment: {e}")
            raise DegradationExhaustedError(levels_attempted=["full"], original_error=e)

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
