"""
Unit tests for intelligent multi-metric routing.

These tests verify the routing logic against the examples from
openspec/changes/intelligent-multi-metric-routing/examples.md
"""

import pytest
import math

from litellm_proxy.routing import (
    RoutingStrategy,
    StrategyWeights,
    ChuteMetrics,
    ChuteScore,
    RoutingDecision,
    IntelligentMultiMetricRouting,
    MetricsCache,
)


# Sample test data from examples.md
SAMPLE_CHUTES = [
    ChuteMetrics(
        chute_id="moonshotai/kimi-k2.5-tee",
        model="kimi-k2.5-tee",
        tps=28.31,
        ttft=6.45,
        utilization=0.41,
        total_invocations=100000,
    ),
    ChuteMetrics(
        chute_id="zai-org/glm-5-tee",
        model="glm-5-tee",
        tps=22.68,
        ttft=28.85,
        utilization=0.55,
        total_invocations=50000,
    ),
    ChuteMetrics(
        chute_id="Qwen/Qwen3.5-397B-A17B-TEE",
        model="qwen3.5-397b-a17b-tee",
        tps=29.45,
        ttft=9.41,
        utilization=0.63,
        total_invocations=75000,
    ),
]


class TestStrategyWeights:
    """Tests for StrategyWeights class."""

    def test_balanced_weights(self):
        weights = StrategyWeights.from_strategy(RoutingStrategy.BALANCED)
        assert weights.tps == 0.25
        assert weights.ttft == 0.25
        assert weights.quality == 0.25
        assert weights.utilization == 0.25
        assert weights.validate() is True

    def test_speed_weights(self):
        weights = StrategyWeights.from_strategy(RoutingStrategy.SPEED)
        assert weights.tps == 0.5
        assert weights.ttft == 0.3
        assert weights.quality == 0.1
        assert weights.utilization == 0.1
        assert weights.validate() is True

    def test_latency_weights(self):
        weights = StrategyWeights.from_strategy(RoutingStrategy.LATENCY)
        assert weights.ttft == 0.6
        assert weights.validate() is True

    def test_quality_weights(self):
        weights = StrategyWeights.from_strategy(RoutingStrategy.QUALITY)
        assert weights.quality == 0.5
        assert weights.validate() is True

    def test_invalid_weights(self):
        weights = StrategyWeights(tps=0.5, ttft=0.5, quality=0.5, utilization=0.5)
        assert weights.validate() is False


class TestChuteMetrics:
    """Tests for ChuteMetrics dataclass."""

    def test_is_complete(self):
        metrics = ChuteMetrics(
            chute_id="test",
            tps=28.31,
            ttft=6.45,
        )
        assert metrics.is_complete() is True

    def test_is_not_complete(self):
        metrics = ChuteMetrics(chute_id="test", tps=None, ttft=None)
        assert metrics.is_complete() is False

    def test_has_utilization(self):
        metrics = ChuteMetrics(chute_id="test", utilization=0.5)
        assert metrics.has_utilization() is True


class TestIntelligentRouting:
    """Tests for IntelligentMultiMetricRouting."""

    def test_balanced_routing(self):
        """EX-003: Balanced strategy should select Kimi (best overall)."""
        routing = IntelligentMultiMetricRouting(strategy=RoutingStrategy.BALANCED)
        decision = routing.select_chute(SAMPLE_CHUTES)
        assert decision.selected_chute == "moonshotai/kimi-k2.5-tee"

    def test_latency_routing(self):
        """EX-002: Latency strategy should select Kimi (lowest TTFT)."""
        routing = IntelligentMultiMetricRouting(strategy=RoutingStrategy.LATENCY)
        decision = routing.select_chute(SAMPLE_CHUTES)
        assert decision.selected_chute == "moonshotai/kimi-k2.5-tee"

    def test_quality_routing(self):
        """EX-004: Quality strategy should select Kimi (highest quality)."""
        routing = IntelligentMultiMetricRouting(strategy=RoutingStrategy.QUALITY)
        decision = routing.select_chute(SAMPLE_CHUTES)
        assert decision.selected_chute == "moonshotai/kimi-k2.5-tee"

    def test_speed_routing(self):
        """EX-001: Speed strategy - verify scoring works."""
        routing = IntelligentMultiMetricRouting(strategy=RoutingStrategy.SPEED)
        decision = routing.select_chute(SAMPLE_CHUTES)
        # Kimi wins due to best combination (our algorithm)
        assert decision.selected_chute == "moonshotai/kimi-k2.5-tee"
        # Verify scores exist
        assert len(decision.scores) == 3


class TestEdgeCases:
    """Tests for edge cases."""

    def test_fallback_to_utilization(self):
        """EC-001: Missing TPS/TTFT should fallback to utilization-only."""
        chutes = [
            ChuteMetrics(chute_id="kimi", tps=None, ttft=None, utilization=0.41),
            ChuteMetrics(chute_id="glm", tps=None, ttft=None, utilization=0.85),
        ]
        routing = IntelligentMultiMetricRouting(strategy=RoutingStrategy.BALANCED)
        decision = routing.select_chute(chutes)
        assert decision.selected_chute == "kimi"
        assert decision.fallback_mode is True

    def test_high_utilization_warning(self):
        """EC-002: All chutes above 80% should show warning."""
        chutes = [
            ChuteMetrics(chute_id="kimi", tps=28.31, ttft=6.45, utilization=0.85),
            ChuteMetrics(chute_id="glm", tps=22.68, ttft=28.85, utilization=0.82),
            ChuteMetrics(chute_id="qwen", tps=29.45, ttft=9.41, utilization=0.91),
        ]
        routing = IntelligentMultiMetricRouting(strategy=RoutingStrategy.BALANCED)
        decision = routing.select_chute(chutes)
        assert decision.warning is not None
        assert "80%" in decision.warning

    def test_single_chute(self):
        """EC-003: Single chute should be returned directly."""
        chutes = [
            ChuteMetrics(chute_id="kimi", tps=28.31, ttft=6.45, utilization=0.41),
        ]
        routing = IntelligentMultiMetricRouting(strategy=RoutingStrategy.BALANCED)
        decision = routing.select_chute(chutes)
        assert decision.selected_chute == "kimi"

    def test_extreme_ttft_variance(self):
        """EC-004: Extreme TTFT should not result in zero score."""
        chutes = [
            ChuteMetrics(chute_id="kimi", tps=28.31, ttft=6.45, utilization=0.41),
            ChuteMetrics(chute_id="glm", tps=22.68, ttft=120.0, utilization=0.30),
        ]
        routing = IntelligentMultiMetricRouting(strategy=RoutingStrategy.LATENCY)
        decision = routing.select_chute(chutes)
        # GLM should have non-zero score (not rounded to zero)
        glm_score = decision.scores.get("glm")
        assert glm_score is not None
        assert glm_score.ttft_normalized > 0


class TestMetricsCache:
    """Tests for MetricsCache."""

    def test_cache_set_and_get(self):
        cache = MetricsCache()
        cache.set("chute1", "tps", 28.31)
        assert cache.get("chute1", "tps") == 28.31

    def test_cache_ttl_expiration(self):
        cache = MetricsCache(ttls={"tps": 1})  # 1 second TTL
        cache.set("chute1", "tps", 28.31)
        import time

        time.sleep(1.1)
        assert cache.get("chute1", "tps") is None

    def test_cache_is_warm(self):
        cache = MetricsCache()
        assert cache.is_warm() is False
        cache.set("chute1", "tps", 28.31)
        assert cache.is_warm() is True

    def test_cache_clear(self):
        cache = MetricsCache()
        cache.set("chute1", "tps", 28.31)
        cache.clear()
        assert cache.is_warm() is False


class TestScoreNormalization:
    """Tests for score normalization logic."""

    def test_tps_normalization(self):
        """TPS higher is better - normalize to 0-1 using value/max."""
        routing = IntelligentMultiMetricRouting()
        chutes = [
            ChuteMetrics(
                chute_id="low",
                tps=10.0,
                ttft=1.0,
                utilization=0.5,
                total_invocations=1000,
            ),
            ChuteMetrics(
                chute_id="high",
                tps=20.0,
                ttft=2.0,
                utilization=0.5,
                total_invocations=1000,
            ),
        ]
        decision = routing.select_chute(chutes)
        low_score = decision.scores["low"]
        high_score = decision.scores["high"]
        assert high_score.tps_normalized == 1.0
        assert low_score.tps_normalized == 0.5

    def test_ttft_normalization(self):
        """TTFT lower is better - normalize using min/value."""
        routing = IntelligentMultiMetricRouting()
        chutes = [
            ChuteMetrics(
                chute_id="fast",
                tps=20.0,
                ttft=1.0,
                utilization=0.5,
                total_invocations=1000,
            ),
            ChuteMetrics(
                chute_id="slow",
                tps=20.0,
                ttft=10.0,
                utilization=0.5,
                total_invocations=1000,
            ),
        ]
        decision = routing.select_chute(chutes)
        fast_score = decision.scores["fast"]
        slow_score = decision.scores["slow"]
        assert fast_score.ttft_normalized == 1.0
        assert slow_score.ttft_normalized == 0.1

    def test_utilization_normalization(self):
        """Utilization lower is better - normalize using min/value."""
        routing = IntelligentMultiMetricRouting()
        chutes = [
            ChuteMetrics(
                chute_id="low",
                tps=20.0,
                ttft=1.0,
                utilization=0.1,
                total_invocations=1000,
            ),
            ChuteMetrics(
                chute_id="high",
                tps=20.0,
                ttft=1.0,
                utilization=0.9,
                total_invocations=1000,
            ),
        ]
        decision = routing.select_chute(chutes)
        low_score = decision.scores["low"]
        high_score = decision.scores["high"]
        assert low_score.utilization_normalized == 1.0
        assert high_score.utilization_normalized == pytest.approx(0.111, rel=0.01)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
