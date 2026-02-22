"""
Integration tests for LiteLLM proxy model selection.

Tests verify that the routing strategy correctly selects models based on
utilization data and handles fallback scenarios.
"""

import pytest
from unittest.mock import Mock
from typing import Dict, Any

from litellm_proxy.routing.strategy import ChutesUtilizationRouting
from litellm_proxy.cache.store import UtilizationCache


@pytest.mark.integration
class TestModelSelection:
    """Integration tests for model selection based on utilization."""

    def test_model_selection_low_utilization(self):
        """
        Given: Multiple models with different utilization levels
        When: Model selection is requested
        Then: Model with lowest utilization should be selected
        """
        # Arrange - Create routing strategy with mock client
        cache = UtilizationCache(ttl=30)
        mock_client = Mock()

        # Define utilization levels for models
        utilizations = {
            "model-a": 0.8,  # High
            "model-b": 0.2,  # Low - should be selected
            "model-c": 0.5,  # Medium
        }

        def mock_get_util(chute_id):
            return utilizations.get(chute_id)

        mock_client.get_utilization = mock_get_util

        routing = ChutesUtilizationRouting(api_client=mock_client, cache=cache)

        # Set up model list
        mock_router = Mock()
        mock_router.model_list = [
            {"model_name": "provider/model-a", "model_info": {"id": "model-a"}},
            {"model_name": "provider/model-b", "model_info": {"id": "model-b"}},
            {"model_name": "provider/model-c", "model_info": {"id": "model-c"}},
        ]
        routing.set_router(mock_router)

        # Act - Get available deployment (which should select lowest utilization)
        deployment = routing.get_available_deployment(
            model="test-model", request_kwargs={"router": mock_router}
        )

        # Assert - Should select model-b (lowest utilization)
        assert deployment is not None
        model_info = deployment.get("model_info", {})
        chute_id = model_info.get("id")
        assert chute_id == "model-b"

    def test_model_selection_high_utilization_fallback(self):
        """
        Given: Primary model has high utilization (saturated)
        When: Model selection is requested
        Then: Should fallback to model with lower utilization
        """
        # Arrange
        cache = UtilizationCache(ttl=30)
        mock_client = Mock()

        # Primary is saturated (0.95), others are available
        utilizations = {
            "model-a": 0.95,  # Almost full - should NOT be selected
            "model-b": 0.3,  # Low - should be selected
            "model-c": 0.6,  # Medium
        }

        def mock_get_util(chute_id):
            return utilizations.get(chute_id)

        mock_client.get_utilization = mock_get_util

        routing = ChutesUtilizationRouting(api_client=mock_client, cache=cache)

        mock_router = Mock()
        mock_router.model_list = [
            {"model_name": "provider/model-a", "model_info": {"id": "model-a"}},
            {"model_name": "provider/model-b", "model_info": {"id": "model-b"}},
            {"model_name": "provider/model-c", "model_info": {"id": "model-c"}},
        ]
        routing.set_router(mock_router)

        # Act
        deployment = routing.get_available_deployment(
            model="provider/model-a", request_kwargs={"router": mock_router}
        )

        # Assert - Should fallback to model-b (lower utilization)
        assert deployment is not None
        model_info = deployment.get("model_info", {})
        chute_id = model_info.get("id")
        # Should NOT select the saturated model
        assert chute_id != "model-a"
        # Should select the lowest utilization
        assert chute_id == "model-b"

    def test_model_selection_all_unhealthy_fallback(self):
        """
        Given: All models are unhealthy (unavailable or returning errors)
        When: Model selection is requested
        Then: Should fallback to default behavior or return first available
        """
        # Arrange
        cache = UtilizationCache(ttl=30)
        mock_client = Mock()

        # All models return None (unavailable)
        call_count = 0

        def mock_get_util(chute_id):
            nonlocal call_count
            call_count += 1
            return None  # All unavailable

        mock_client.get_utilization = mock_get_util

        routing = ChutesUtilizationRouting(api_client=mock_client, cache=cache)

        mock_router = Mock()
        mock_router.model_list = [
            {"model_name": "provider/model-a", "model_info": {"id": "model-a"}},
            {"model_name": "provider/model-b", "model_info": {"id": "model-b"}},
            {"model_name": "provider/model-c", "model_info": {"id": "model-c"}},
        ]
        routing.set_router(mock_router)

        # Act - Get utilization for all models
        utilizations = routing._get_all_utilizations(mock_router.model_list)

        # Assert - All models get default value (0.5) when unavailable
        assert "model-a" in utilizations
        assert "model-b" in utilizations
        assert "model-c" in utilizations
        # All should have default value
        assert all(util == 0.5 for util in utilizations.values())

        # Act - Get deployment should still return something
        deployment = routing.get_available_deployment(
            model="test-model", request_kwargs={"router": mock_router}
        )

        # Assert - Should return first model as fallback
        assert deployment is not None


@pytest.mark.integration
class TestModelSelectionEdgeCases:
    """Integration tests for edge cases in model selection."""

    def test_model_selection_equal_utilization(self):
        """
        Given: All models have equal utilization
        When: Model selection is requested
        Then: Should deterministically select first model (round-robin-like)
        """
        # Arrange
        cache = UtilizationCache(ttl=30)
        mock_client = Mock()

        # All equal utilization
        utilizations = {
            "model-a": 0.5,
            "model-b": 0.5,
            "model-c": 0.5,
        }

        def mock_get_util(chute_id):
            return utilizations.get(chute_id)

        mock_client.get_utilization = mock_get_util

        routing = ChutesUtilizationRouting(api_client=mock_client, cache=cache)

        mock_router = Mock()
        mock_router.model_list = [
            {"model_name": "provider/model-a", "model_info": {"id": "model-a"}},
            {"model_name": "provider/model-b", "model_info": {"id": "model-b"}},
            {"model_name": "provider/model-c", "model_info": {"id": "model-c"}},
        ]
        routing.set_router(mock_router)

        # Act - Make multiple selections
        results = []
        for _ in range(3):
            deployment = routing.get_available_deployment(
                model="test-model", request_kwargs={"router": mock_router}
            )
            if deployment:
                results.append(deployment.get("model_info", {}).get("id"))

        # Assert - All should be the same (first model) due to deterministic behavior
        # Python's min() returns first item with minimum value
        assert len(set(results)) == 1  # All same
        assert results[0] == "model-a"  # First one selected

    def test_model_selection_cache_impact(self):
        """
        Given: Cache has stale data
        When: New request comes in
        Then: Should use cached data if within TTL
        """
        # Arrange
        cache = UtilizationCache(ttl=30)
        mock_client = Mock()

        call_count = 0

        def mock_get_util(chute_id):
            nonlocal call_count
            call_count += 1
            # First call returns 0.2, subsequent would return different
            if call_count == 1:
                return 0.2
            return 0.8

        mock_client.get_utilization = mock_get_util

        routing = ChutesUtilizationRouting(api_client=mock_client, cache=cache)

        mock_router = Mock()
        mock_router.model_list = [
            {"model_name": "provider/model-a", "model_info": {"id": "model-a"}},
        ]
        routing.set_router(mock_router)

        # First request - should hit API
        util1 = routing._get_utilization("model-a")
        assert util1 == 0.2
        assert call_count == 1

        # Second request within TTL - should use cache
        util2 = routing._get_utilization("model-a")
        assert util2 == 0.2
        assert call_count == 1  # Still 1, didn't call API again

        # Verify cache is working
        cached = cache.get("model-a")
        assert cached == 0.2
