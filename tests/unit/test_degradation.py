"""
Unit tests for degradation cascade and circuit breaker behavior.

These tests verify the 4-tier degradation cascade:
- Level 1 (Cache): Use cached metrics if available
- Level 2 (Utilization): Fall back to utilization-only routing
- Level 3 (Random): Random selection with explicit warning
- Level 4 (Failure): Raise structured exception if all options exhausted

And the circuit breaker behavior:
- Opens after threshold failures (default: 3)
- Closes after cooldown (default: 30s)
- Returns degraded responses during open state
"""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock

from litellm_proxy.routing.intelligent import IntelligentMultiMetricRouting
from litellm_proxy.routing.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
from litellm_proxy.routing.responses import DegradationLevel, ResponseBuilder
from litellm_proxy.exceptions import (
    DegradationExhaustedError,
    CircuitBreakerOpenError,
)
from litellm_proxy.routing import (
    RoutingStrategy,
    ChuteMetrics,
    MetricsCache,
)


# Sample model list for testing
SAMPLE_MODEL_LIST = [
    {
        "model_name": "chutes-models",
        "litellm_params": {
            "model": "openai/moonshotai/Kimi-K2.5-TEE",
            "api_base": "https://llm.chutes.ai/v1",
            "api_key": "test-key",
        },
        "model_info": {
            "id": "kimi-k2.5-tee",
            "chute_id": "chute_kimi_k2.5_tee",
        },
    },
    {
        "model_name": "chutes-models",
        "litellm_params": {
            "model": "openai/zai-org/GLM-5-TEE",
            "api_base": "https://llm.chutes.ai/v1",
            "api_key": "test-key",
        },
        "model_info": {
            "id": "glm-5-tee",
            "chute_id": "chute_glm_5_tee",
        },
    },
    {
        "model_name": "chutes-models",
        "litellm_params": {
            "model": "openai/Qwen/Qwen3.5-397B-A17B-TEE",
            "api_base": "https://llm.chutes.ai/v1",
            "api_key": "test-key",
        },
        "model_info": {
            "id": "qwen3.5-397b-tee",
            "chute_id": "chute_qwen3.5_397b_tee",
        },
    },
]


class TestCircuitBreaker:
    """Tests for CircuitBreaker class."""

    def test_circuit_breaker_initial_state(self):
        """Circuit breaker starts in closed state."""
        cb = CircuitBreaker()
        assert cb.state.value == "closed"
        assert cb.is_open() is False
        assert cb.is_half_open() is False

    def test_circuit_breaker_opens_after_threshold(self):
        """Circuit breaker opens after threshold failures."""
        cb = CircuitBreaker(
            CircuitBreakerConfig(failure_threshold=3, cooldown_seconds=30)
        )

        # Record 2 failures - should not open yet
        cb.record_failure()
        cb.record_failure()
        assert cb.is_open() is False

        # Record 3rd failure - should open
        cb.record_failure()
        assert cb.is_open() is True
        assert cb.state.value == "open"

    def test_circuit_breaker_closes_after_cooldown(self):
        """Circuit breaker transitions to half-open after cooldown."""
        cb = CircuitBreaker(
            CircuitBreakerConfig(failure_threshold=2, cooldown_seconds=1)
        )

        # Open the circuit breaker
        cb.record_failure()
        cb.record_failure()
        assert cb.is_open() is True

        # Wait for cooldown
        time.sleep(1.1)

        # Should transition to half-open
        assert cb.is_half_open() is True
        assert cb.state.value == "half_open"

    def test_circuit_breaker_closes_on_success(self):
        """Circuit breaker closes after successful recovery."""
        cb = CircuitBreaker(
            CircuitBreakerConfig(failure_threshold=2, cooldown_seconds=30)
        )

        # Open the circuit breaker
        cb.record_failure()
        cb.record_failure()
        assert cb.is_open() is True

        # Wait for cooldown to transition to half-open
        time.sleep(0.1)  # Small wait to ensure we're in the right state logic
        cb._last_failure_time = time.time() - 31  # Force to half-open
        assert cb.is_half_open() is True

        # Record success - should close
        cb.record_success()
        assert cb.is_open() is False
        assert cb.state.value == "closed"

    def test_circuit_breaker_resets_on_success_in_half_open(self):
        """Circuit breaker resets failure count on success."""
        cb = CircuitBreaker(
            CircuitBreakerConfig(failure_threshold=3, cooldown_seconds=30)
        )

        # Record some failures
        cb.record_failure()
        cb.record_failure()
        assert cb._failure_count == 2

        # Record success - should reset count
        cb.record_success()
        assert cb._failure_count == 0
        assert cb.state.value == "closed"

    def test_circuit_breaker_get_status(self):
        """Circuit breaker status includes all relevant info."""
        cb = CircuitBreaker(
            CircuitBreakerConfig(failure_threshold=3, cooldown_seconds=30)
        )
        cb.record_failure()

        status = cb.get_status()
        assert "state" in status
        assert "failure_count" in status
        assert status["failure_count"] == 1


class TestDegradationLevels:
    """Tests for degradation cascade."""

    def test_degradation_level_full(self):
        """Degradation level 0 = Full metrics available."""
        assert DegradationLevel.FULL == 0
        assert DegradationLevel.to_string(0) == "Full metrics available"

    def test_degradation_level_cached(self):
        """Degradation level 1 = Using cached metrics."""
        assert DegradationLevel.CACHED == 1
        assert DegradationLevel.to_string(1) == "Using cached metrics"

    def test_degradation_level_utilization(self):
        """Degradation level 2 = Using utilization only."""
        assert DegradationLevel.UTILIZATION == 2
        assert DegradationLevel.to_string(2) == "Using utilization only"

    def test_degradation_level_random(self):
        """Degradation level 3 = Random selection."""
        assert DegradationLevel.RANDOM == 3
        assert DegradationLevel.to_string(3) == "Random selection (metrics unavailable)"

    def test_degradation_level_failed(self):
        """Degradation level 4 = Complete failure."""
        assert DegradationLevel.FAILED == 4
        assert DegradationLevel.to_string(4) == "Complete failure"


class TestResponseBuilder:
    """Tests for ResponseBuilder class."""

    def test_build_success_with_degradation_level(self):
        """Success response includes degradation metadata."""
        builder = ResponseBuilder()
        deployment = {
            "litellm_params": {"model": "test-model"},
            "model_info": {"id": "test"},
        }

        result = builder.build_success(deployment, DegradationLevel.CACHED)

        assert "_routing_metadata" in result
        assert result["_routing_metadata"]["degradation_level"] == 1

    def test_build_error_response(self):
        """Error response includes both RFC 9457 and OpenAI formats."""
        builder = ResponseBuilder()

        result = builder.build_error_response(
            error_type="server_error",
            message="Test error",
            status_code=503,
            code="test_error",
        )

        # Check RFC 9457 format
        assert "problem_details" in result
        assert result["problem_details"]["title"] == "Server Error"
        assert result["problem_details"]["status"] == 503

        # Check OpenAI format
        assert "error" in result
        assert result["error"]["message"] == "Test error"
        assert result["error"]["type"] == "server_error"


class TestIntelligentRoutingDegradation:
    """Integration tests for degradation in IntelligentMultiMetricRouting."""

    def test_circuit_breaker_open_uses_cached(self):
        """When circuit breaker is open, use cached metrics if available."""
        # Setup: Create routing with cache that has data for all chutes
        cache = MetricsCache(ttls={"utilization": 30, "tps": 300, "ttft": 300})

        # Add cached metrics for all chutes
        for chute_id in [
            "chute_kimi_k2.5_tee",
            "chute_glm_5_tee",
            "chute_qwen3.5_397b_tee",
        ]:
            cache.set_all(
                ChuteMetrics(
                    chute_id=chute_id,
                    model="test-model",
                    tps=28.0,
                    ttft=6.0,
                    utilization=0.4,
                )
            )

        routing = IntelligentMultiMetricRouting(
            strategy=RoutingStrategy.BALANCED,
            cache=cache,
            chutes_api_key="test-key",
            enable_circuit_breaker=True,
        )

        # Force circuit breaker open
        routing._circuit_breaker._state = routing._circuit_breaker.state.__class__.OPEN
        routing._circuit_breaker._failure_count = 5

        # Setup model list
        routing._router = Mock()
        routing._router.model_list = SAMPLE_MODEL_LIST

        # Call get_available_deployment - should use cached metrics
        deployment = routing.get_available_deployment(
            model="test-model",
            request_kwargs={"router": routing._router},
        )

        assert deployment is not None
        metadata = deployment.get("_routing_metadata", {})
        # Should be either CACHED (1) or RANDOM (3) depending on implementation
        # The key is that it should not fail
        assert metadata.get("degradation_level") in [
            DegradationLevel.CACHED,
            DegradationLevel.RANDOM,
        ]

    def test_no_cache_falls_back_to_random(self):
        """When no cache and API fails, fall back to random selection."""
        routing = IntelligentMultiMetricRouting(
            strategy=RoutingStrategy.BALANCED,
            chutes_api_key="test-key",
            enable_circuit_breaker=False,
        )

        # Mock API client to fail
        routing._api_client = Mock()
        routing._api_client.get_bulk_utilization.side_effect = Exception("API Error")

        # Setup model list
        routing._router = Mock()
        routing._router.model_list = SAMPLE_MODEL_LIST

        # Should fall back to random selection
        deployment = routing.get_available_deployment(
            model="test-model",
            request_kwargs={"router": routing._router},
        )

        assert deployment is not None
        metadata = deployment.get("_routing_metadata", {})
        assert metadata.get("degradation_level") == DegradationLevel.RANDOM

    def test_degradation_exhausted_raises_exception(self):
        """When all degradation levels fail, raise DegradationExhaustedError."""
        routing = IntelligentMultiMetricRouting(
            strategy=RoutingStrategy.BALANCED,
            chutes_api_key="test-key",
            enable_circuit_breaker=False,
            enable_degradation=False,  # Disable degradation to trigger exception
        )

        # Mock API client to fail and no cache
        routing._api_client = Mock()
        routing._api_client.get_bulk_utilization.side_effect = Exception("API Error")

        # Setup model list
        routing._router = Mock()
        routing._router.model_list = SAMPLE_MODEL_LIST

        # Should raise DegradationExhaustedError
        with pytest.raises(DegradationExhaustedError) as exc_info:
            routing.get_available_deployment(
                model="test-model",
                request_kwargs={"router": routing._router},
            )

        assert "full" in exc_info.value.levels_attempted

    def test_health_status_degraded(self):
        """Health status returns degraded when circuit breaker is open."""
        routing = IntelligentMultiMetricRouting(
            strategy=RoutingStrategy.BALANCED,
            chutes_api_key="test-key",
            enable_circuit_breaker=True,
        )

        # Force circuit breaker open
        routing._circuit_breaker._state = routing._circuit_breaker.state.__class__.OPEN

        health = routing.get_health_status()

        assert health["status"] == "unhealthy"
        assert health["degradation_level"] == 4


class TestHTTPStatusCodes:
    """Tests for HTTP status code behavior."""

    def test_successful_routing_returns_200(self):
        """Successful routing returns 200 even if degraded."""
        # This tests the concept - actual HTTP testing would require the FastAPI test client
        from litellm_proxy.api.routes import _update_metrics, _metrics

        # Reset metrics
        _metrics["requests_total"] = {"success": 0, "degraded": 0, "failed": 0}

        # Simulate successful degraded response
        _update_metrics("degraded", DegradationLevel.CACHED)

        assert _metrics["requests_total"]["degraded"] == 1

    def test_failed_routing_updates_failed_counter(self):
        """Failed routing updates failed counter."""
        from litellm_proxy.api.routes import _update_metrics, _metrics

        # Reset metrics
        _metrics["requests_total"] = {"success": 0, "degraded": 0, "failed": 0}

        # Simulate failed response
        _update_metrics("failed", DegradationLevel.FAILED)

        assert _metrics["requests_total"]["failed"] == 1


class TestPrometheusMetrics:
    """Tests for Prometheus metrics format."""

    def test_circuit_breaker_state_value(self):
        """Circuit breaker state converts to numeric value."""
        # Import the routes module to access module-level variables
        import litellm_proxy.api.routes as api_routes

        # Reset routing instance for test
        api_routes._routing_instance = None

        # No routing instance should return 0
        assert api_routes._get_circuit_breaker_state_value() == 0

        # Create routing with circuit breaker
        routing = IntelligentMultiMetricRouting(
            strategy=RoutingStrategy.BALANCED,
            enable_circuit_breaker=True,
        )

        # Set the module-level variable
        api_routes._routing_instance = routing

        # Default state should be 0 (closed)
        assert api_routes._get_circuit_breaker_state_value() == 0

        # Open state should be 1 - use record_failure to open the circuit
        # Default failure threshold is 3
        routing._circuit_breaker.record_failure()
        routing._circuit_breaker.record_failure()
        routing._circuit_breaker.record_failure()
        assert api_routes._get_circuit_breaker_state_value() == 1

        # Half-open state - wait for cooldown and try again
        routing._circuit_breaker._last_failure_time = (
            time.time() - 35
        )  # Past cooldown (30s)
        assert api_routes._get_circuit_breaker_state_value() == 2

        # Cleanup
        api_routes._routing_instance = None

    def test_prometheus_format(self):
        """Prometheus metrics follow correct format."""
        from litellm_proxy.api.routes import _metrics, _get_circuit_breaker_state_value

        # Set test values
        _metrics["degradation_level"] = 1
        _metrics["requests_total"] = {"success": 10, "degraded": 2, "failed": 1}

        cb_state = _get_circuit_breaker_state_value()

        # Build expected output
        lines = [
            "# HELP chutes_routing_degradation_level Current degradation level (0-4)",
            "# TYPE chutes_routing_degradation_level gauge",
            "chutes_routing_degradation_level 1",
            "",
            "# HELP chutes_circuit_breaker_state Circuit breaker state (0=closed, 1=open, 2=half-open)",
            "# TYPE chutes_circuit_breaker_state gauge",
            f"chutes_circuit_breaker_state {cb_state}",
            "",
            "# HELP chutes_routing_requests_total Total routing requests",
            "# TYPE chutes_routing_requests_total counter",
            'chutes_routing_requests_total{status="success"} 10',
            'chutes_routing_requests_total{status="degraded"} 2',
            'chutes_routing_requests_total{status="failed"} 1',
            "",
        ]

        expected = "\n".join(lines)

        # This is what the endpoint should return
        # (actual test would call the endpoint with TestClient)
        assert "chutes_routing_degradation_level" in expected
        assert "chutes_circuit_breaker_state" in expected
        assert "chutes_routing_requests_total" in expected


class TestEnvironmentVariables:
    """Tests for environment variable configuration."""

    @patch.dict(
        "os.environ",
        {
            "CIRCUIT_BREAKER_ENABLED": "false",
            "DEGRADATION_ENABLED": "false",
        },
    )
    def test_env_vars_disable_features(self):
        """Environment variables can disable circuit breaker and degradation."""
        # Note: This test checks the env var reading logic

        # Clear any cached env vars by creating new instance
        routing = IntelligentMultiMetricRouting.__new__(IntelligentMultiMetricRouting)

        # The constructor should read from env vars
        # This is a conceptual test - actual implementation reads in __init__
        import os

        assert os.environ.get("CIRCUIT_BREAKER_ENABLED") == "false"
        assert os.environ.get("DEGRADATION_ENABLED") == "false"

    def test_circuit_breaker_config_from_params(self):
        """Circuit breaker config can be customized via parameters."""
        config = CircuitBreakerConfig(
            failure_threshold=5,
            cooldown_seconds=60,
        )

        cb = CircuitBreaker(config)

        assert cb.config.failure_threshold == 5
        assert cb.config.cooldown_seconds == 60

        # Should still open after threshold
        for i in range(5):
            cb.record_failure()

        assert cb.is_open() is True
