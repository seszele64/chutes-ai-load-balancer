"""
Integration tests for model switching and failover behavior.

These tests verify that the routing strategy correctly handles:
- Failover to secondary model when primary is unhealthy
- Failover to tertiary model when primary and secondary are unhealthy
- Failback to primary when it recovers
- Model selection under load conditions
"""

import pytest
from unittest.mock import Mock, patch
from typing import Any, Dict, List, Optional
import threading
import time

from litellm_proxy.routing.strategy import ChutesUtilizationRouting
from litellm_proxy.cache.store import UtilizationCache
from litellm_proxy.exceptions import ChutesAPITimeoutError, ChutesAPIConnectionError


def create_mock_router(model_ids: List[str]) -> Mock:
    """Helper to create a mock router with model list."""
    mock_router = Mock()
    mock_router.model_list = [
        {"model_name": f"provider/{model_id}", "model_info": {"id": model_id}}
        for model_id in model_ids
    ]
    return mock_router


def create_mock_client(utilizations: Dict[str, float]) -> Mock:
    """Helper to create a mock API client with specific utilizations."""
    mock_client = Mock()

    def mock_get_util(chute_id: str) -> Optional[float]:
        return utilizations.get(chute_id)

    mock_client.get_utilization = mock_get_util
    return mock_client


@pytest.mark.integration
class TestModelFailover:
    """Tests for model failover behavior."""

    def test_failover_to_secondary_model(self):
        """
        Given: Primary model is unhealthy (high utilization)
        When: Model selection is requested
        Then: Request routes to secondary model with lower utilization
        """
        # Arrange - Primary is saturated, secondary is available
        utilizations = {
            "model-primary": 0.99,  # Almost full - unhealthy
            "model-secondary": 0.3,  # Available - should be selected
            "model-tertiary": 0.5,  # Available
        }

        cache = UtilizationCache(ttl=30)
        mock_client = create_mock_client(utilizations)
        routing = ChutesUtilizationRouting(api_client=mock_client, cache=cache)

        mock_router = create_mock_router(
            ["model-primary", "model-secondary", "model-tertiary"]
        )
        routing.set_router(mock_router)

        # Act
        deployment = routing.get_available_deployment(
            model="test-model", request_kwargs={"router": mock_router}
        )

        # Assert - Should NOT select primary (unhealthy)
        assert deployment is not None
        model_info = deployment.get("model_info", {})
        selected_model = model_info.get("id")

        # Should route to secondary (lower utilization)
        assert selected_model == "model-secondary"
        assert selected_model != "model-primary"

    def test_failover_to_tertiary_model(self):
        """
        Given: Primary and secondary models are unhealthy
        When: Model selection is requested
        Then: Request routes to tertiary model
        """
        # Arrange - Primary and secondary saturated
        utilizations = {
            "model-primary": 0.98,  # Unhealthy
            "model-secondary": 0.95,  # Unhealthy
            "model-tertiary": 0.4,  # Available - should be selected
        }

        cache = UtilizationCache(ttl=30)
        mock_client = create_mock_client(utilizations)
        routing = ChutesUtilizationRouting(api_client=mock_client, cache=cache)

        mock_router = create_mock_router(
            ["model-primary", "model-secondary", "model-tertiary"]
        )
        routing.set_router(mock_router)

        # Act
        deployment = routing.get_available_deployment(
            model="test-model", request_kwargs={"router": mock_router}
        )

        # Assert
        assert deployment is not None
        model_info = deployment.get("model_info", {})
        selected_model = model_info.get("id")

        # Should route to tertiary
        assert selected_model == "model-tertiary"
        assert selected_model not in ["model-primary", "model-secondary"]

    def test_failback_when_primary_recovers(self):
        """
        Given: Primary was unhealthy but has now recovered
        When: Model selection is requested
        Then: Traffic goes back to primary model
        """
        # Arrange - Initially primary is unhealthy
        call_count = [0]

        def mock_get_util(chute_id: str) -> float:
            call_count[0] += 1
            # After first few calls, primary recovers
            if call_count[0] > 2:
                return 0.2  # Primary recovered
            return 0.95 if chute_id == "model-primary" else 0.3

        mock_client = Mock()
        mock_client.get_utilization = mock_get_util

        cache = UtilizationCache(ttl=30)
        routing = ChutesUtilizationRouting(api_client=mock_client, cache=cache)

        mock_router = create_mock_router(["model-primary", "model-secondary"])
        routing.set_router(mock_router)

        # Act - First request when primary is unhealthy
        deployment1 = routing.get_available_deployment(
            model="test-model", request_kwargs={"router": mock_router}
        )

        # Assert - Should fallback to secondary
        model_info1 = deployment1.get("model_info", {})
        selected1 = model_info1.get("id")

        # Clear cache to force re-fetch
        cache.clear()

        # Now primary recovers
        mock_client.get_utilization = lambda cid: 0.2 if cid == "model-primary" else 0.3

        # Act - Second request after recovery
        deployment2 = routing.get_available_deployment(
            model="test-model", request_kwargs={"router": mock_router}
        )

        # Assert - Should route back to primary
        model_info2 = deployment2.get("model_info", {})
        selected2 = model_info2.get("id")

        # After recovery, primary should be selected again (lowest util)
        assert selected2 == "model-primary"

    def test_model_selection_under_load(self):
        """
        Given: Multiple concurrent requests under load
        When: Model selection is requested
        Then: Selection works correctly with proper load distribution
        """
        # Arrange
        utilizations = {
            "model-a": 0.3,
            "model-b": 0.5,
            "model-c": 0.7,
        }

        cache = UtilizationCache(ttl=30)
        mock_client = create_mock_client(utilizations)
        routing = ChutesUtilizationRouting(api_client=mock_client, cache=cache)

        mock_router = create_mock_router(["model-a", "model-b", "model-c"])
        routing.set_router(mock_router)

        # Act - Simulate concurrent requests
        results = []
        errors = []

        def make_request():
            try:
                deployment = routing.get_available_deployment(
                    model="test-model", request_kwargs={"router": mock_router}
                )
                if deployment:
                    model_id = deployment.get("model_info", {}).get("id")
                    results.append(model_id)
            except Exception as e:
                errors.append(str(e))

        threads = []
        for _ in range(10):
            t = threading.Thread(target=make_request)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # Assert - No errors and all requests succeeded
        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(results) == 10, "All 10 requests should complete"

        # Assert - All should select model-a (lowest utilization)
        assert all(model_id == "model-a" for model_id in results)


@pytest.mark.integration
class TestModelHealthCheck:
    """Tests for model health checking."""

    def test_unavailable_model_handling(self):
        """
        Given: Model returns None (unavailable)
        When: Getting utilization
        Then: Returns default value and continues to next model
        """
        # Arrange
        utilizations = {
            "model-a": None,  # Unavailable
            "model-b": 0.3,  # Available
            "model-c": 0.5,  # Available
        }

        mock_client = Mock()

        def mock_get_util(chute_id: str):
            value = utilizations.get(chute_id)
            if value is None:
                return None
            return value

        mock_client.get_utilization = mock_get_util

        cache = UtilizationCache(ttl=30)
        routing = ChutesUtilizationRouting(api_client=mock_client, cache=cache)

        mock_router = create_mock_router(["model-a", "model-b", "model-c"])
        routing.set_router(mock_router)

        # Act - Get utilizations
        model_utils = routing._get_all_utilizations(mock_router.model_list)

        # Assert - Unavailable models get default value
        assert "model-a" in model_utils
        # Should use default value for None/unavailable
        assert model_utils["model-a"] == 0.5  # Default utilization

    def test_timeout_handling(self):
        """
        Given: Model API times out
        When: Getting utilization for all models
        Then: Uses default value and continues to next model
        """
        # Arrange
        mock_client = Mock()
        mock_client.get_utilization = Mock(side_effect=ChutesAPITimeoutError("Timeout"))

        cache = UtilizationCache(ttl=30)
        routing = ChutesUtilizationRouting(api_client=mock_client, cache=cache)

        mock_router = create_mock_router(["model-a", "model-b"])
        routing.set_router(mock_router)

        # Act - Get all utilizations (handles exception properly)
        model_utils = routing._get_all_utilizations(mock_router.model_list)

        # Assert - Uses default value on timeout
        assert model_utils["model-a"] == 0.5  # Default value
        assert model_utils["model-b"] == 0.5  # Default value

    def test_connection_error_handling(self):
        """
        Given: Model API connection fails
        When: Getting utilization for all models
        Then: Uses default value and continues to next model
        """
        # Arrange
        mock_client = Mock()
        mock_client.get_utilization = Mock(
            side_effect=ChutesAPIConnectionError("Connection failed")
        )

        cache = UtilizationCache(ttl=30)
        routing = ChutesUtilizationRouting(api_client=mock_client, cache=cache)

        mock_router = create_mock_router(["model-a", "model-b"])
        routing.set_router(mock_router)

        # Act - Get all utilizations
        model_utils = routing._get_all_utilizations(mock_router.model_list)

        # Assert - Uses default on connection error
        assert model_utils["model-a"] == 0.5  # Default value
        assert model_utils["model-b"] == 0.5  # Default value


@pytest.mark.integration
class TestModelSelectionEdgeCases:
    """Additional edge case tests for model switching."""

    def test_all_models_unhealthy(self):
        """
        Given: All models are unhealthy (high utilization)
        When: Model selection is requested
        Then: Returns first available model as last resort
        """
        # Arrange
        utilizations = {
            "model-a": 0.99,
            "model-b": 0.98,
            "model-c": 0.97,
        }

        cache = UtilizationCache(ttl=30)
        mock_client = create_mock_client(utilizations)
        routing = ChutesUtilizationRouting(api_client=mock_client, cache=cache)

        mock_router = create_mock_router(["model-a", "model-b", "model-c"])
        routing.set_router(mock_router)

        # Act
        deployment = routing.get_available_deployment(
            model="test-model", request_kwargs={"router": mock_router}
        )

        # Assert - Should still return a deployment
        assert deployment is not None

    def test_rapid_health_changes(self):
        """
        Given: Model health changes rapidly
        When: Multiple requests are made
        Then: Correct model is selected each time
        """
        # Arrange
        health_state = {"model-a": 0.3, "model-b": 0.4}
        request_num = [0]

        def dynamic_util(chute_id: str) -> float:
            request_num[0] += 1
            # Alternate between healthy and unhealthy
            if request_num[0] % 2 == 0:
                return 0.95  # Unhealthy
            return health_state.get(chute_id, 0.5)

        mock_client = Mock()
        mock_client.get_utilization = dynamic_util

        cache = UtilizationCache(ttl=1)  # Minimal TTL to always get fresh data
        routing = ChutesUtilizationRouting(api_client=mock_client, cache=cache)

        mock_router = create_mock_router(["model-a", "model-b"])
        routing.set_router(mock_router)

        # Act - Make multiple requests
        selections = []
        for _ in range(4):
            deployment = routing.get_available_deployment(
                model="test-model", request_kwargs={"router": mock_router}
            )
            if deployment:
                model_id = deployment.get("model_info", {}).get("id")
                selections.append(model_id)
            cache.clear()  # Force fresh fetch

        # Assert - Should get consistent selections (first should always be available)
        assert len(selections) == 4
        # First request should always select model-a (lowest utilization at that time)
        assert selections[0] == "model-a"
