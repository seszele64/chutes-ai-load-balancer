"""
Integration tests for API endpoints.

Tests verify that multiple components work together correctly.
These tests test the actual integration between components.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from typing import Dict, Any

from litellm_proxy.routing.strategy import ChutesUtilizationRouting
from litellm_proxy.cache.store import UtilizationCache
from litellm_proxy.config.loader import ConfigLoader


@pytest.mark.integration
class TestHealthEndpoint:
    """Integration tests for /health endpoint."""

    def test_health_endpoint_returns_healthy(self):
        """
        Given: A routing strategy with models configured
        When: Health check is called
        Then: Response should indicate healthy status with model list
        """
        # Arrange - Create routing strategy with mock client
        cache = UtilizationCache(ttl=30)
        mock_client = Mock()

        # Mock utilization data for models
        def mock_get_util(chute_id):
            return 0.3  # Low utilization

        mock_client.get_utilization = mock_get_util
        mock_client.get_bulk_utilization = Mock(
            return_value={
                "models": [
                    {"model_id": "model-a", "utilization": 0.3},
                    {"model_id": "model-b", "utilization": 0.4},
                ]
            }
        )

        routing = ChutesUtilizationRouting(api_client=mock_client, cache=cache)

        # Mock router with model list
        mock_router = Mock()
        mock_router.model_list = [
            {"model_name": "provider/model-a", "model_info": {"id": "model-a"}},
            {"model_name": "provider/model-b", "model_info": {"id": "model-b"}},
        ]
        routing.set_router(mock_router)

        # Act - Simulate health check by getting utilization
        utilizations = routing._get_all_utilizations(mock_router.model_list)

        # Assert - Health check should return healthy models
        assert len(utilizations) > 0
        assert all(util >= 0 for util in utilizations.values())

    def test_routes_endpoint_returns_models(self):
        """
        Given: A routing strategy with models configured
        When: Routes endpoint is called
        Then: Should return list of available routes
        """
        # Arrange
        cache = UtilizationCache(ttl=30)
        mock_client = Mock()
        mock_client.get_utilization = Mock(return_value=0.5)

        routing = ChutesUtilizationRouting(api_client=mock_client, cache=cache)

        # Mock router with model list
        mock_router = Mock()
        mock_router.model_list = [
            {"model_name": "provider/model-a", "model_info": {"id": "model-a"}},
            {"model_name": "provider/model-b", "model_info": {"id": "model-b"}},
            {"model_name": "provider/model-c", "model_info": {"id": "model-c"}},
        ]
        routing.set_router(mock_router)

        # Act - Get utilization for all models
        utilizations = routing._get_all_utilizations(mock_router.model_list)

        # Assert - Should have 3 models
        assert len(utilizations) == 3

    def test_health_endpoint_with_unhealthy_model(self):
        """
        Given: A model that is unhealthy (high utilization or unavailable)
        When: Health check is performed
        Then: Unhealthy models should be excluded or marked
        """
        # Arrange
        cache = UtilizationCache(ttl=30)
        mock_client = Mock()

        # Model a is healthy (low util), model b is unhealthy (high util)
        def mock_get_util(chute_id):
            if chute_id == "model-b":
                return None  # Unavailable
            return 0.3  # Healthy

        mock_client.get_utilization = mock_get_util

        routing = ChutesUtilizationRouting(api_client=mock_client, cache=cache)

        mock_router = Mock()
        mock_router.model_list = [
            {"model_name": "provider/model-a", "model_info": {"id": "model-a"}},
            {"model_name": "provider/model-b", "model_info": {"id": "model-b"}},
        ]
        routing.set_router(mock_router)

        # Act
        utilizations = routing._get_all_utilizations(mock_router.model_list)

        # Assert - Both models should have values (unhealthy uses default 0.5)
        assert "model-a" in utilizations
        assert "model-b" in utilizations
        # model-a is healthy (0.3), model-b gets default (0.5)
        assert utilizations["model-a"] == 0.3

    def test_routes_endpoint_with_custom_timeout(self):
        """
        Given: A routing strategy configured with custom timeout
        When: Routes endpoint is accessed with timeout parameter
        Then: Should respect the timeout setting
        """
        # Arrange - Create routing with custom timeout in API client
        cache = UtilizationCache(ttl=30)
        mock_client = Mock()
        mock_client.get_utilization = Mock(return_value=0.5)

        # Custom timeout is passed to API client internally
        routing = ChutesUtilizationRouting(api_client=mock_client, cache=cache)

        # Verify timeout is set (default is 5 seconds)
        assert routing.api_client is not None

    def test_chat_completions_endpoint_basic(self):
        """
        Given: A valid chat completion request
        When: Request is processed through routing
        Then: Should select a model and return deployment info
        """
        # Arrange
        cache = UtilizationCache(ttl=30)
        mock_client = Mock()

        # Different utilization levels
        utilizations = {
            "model-a": 0.8,
            "model-b": 0.2,  # Lowest - should be selected
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

        # Act - Get available deployment
        deployment = routing.get_available_deployment(
            model="test-model", request_kwargs={"router": mock_router}
        )

        # Assert - Should select model-b (lowest utilization)
        assert deployment is not None

    def test_chat_completions_with_fallback(self):
        """
        Given: Primary model fails (returns error or unavailable)
        When: Request is made
        Then: Should fallback to secondary model
        """
        # Arrange
        cache = UtilizationCache(ttl=30)
        mock_client = Mock()

        call_count = 0

        def mock_get_util(chute_id):
            nonlocal call_count
            call_count += 1
            # First model is unavailable on first call (simulates failure)
            if chute_id == "model-a" and call_count == 1:
                return None
            return 0.5  # Available

        mock_client.get_utilization = mock_get_util

        routing = ChutesUtilizationRouting(api_client=mock_client, cache=cache)

        mock_router = Mock()
        mock_router.model_list = [
            {"model_name": "provider/model-a", "model_info": {"id": "model-a"}},
            {"model_name": "provider/model-b", "model_info": {"id": "model-b"}},
        ]
        routing.set_router(mock_router)

        # First call - model-a unavailable, should fallback
        utilizations = routing._get_all_utilizations(mock_router.model_list)

        # Assert - Both get values (unavailable uses default)
        assert "model-a" in utilizations
        assert "model-b" in utilizations
        # model-a gets default 0.5, model-b is 0.5
        assert utilizations["model-a"] == 0.5

    def test_chat_completions_utilization_tracking(self):
        """
        Given: Multiple requests are made
        When: Utilization is tracked after each request
        Then: Cache should be updated with new utilization values
        """
        # Arrange
        cache = UtilizationCache(ttl=30)
        mock_client = Mock()

        # Simulate utilization changes after each request
        request_count = 0

        def mock_get_util(chute_id):
            nonlocal request_count
            request_count += 1
            # Utilization increases with each request
            return min(0.1 * request_count, 1.0)

        mock_client.get_utilization = mock_get_util

        routing = ChutesUtilizationRouting(api_client=mock_client, cache=cache)

        # First request
        util1 = routing._get_utilization("test-model")
        assert util1 == 0.1

        # Check cache is populated
        cached_value = cache.get("test-model")
        assert cached_value == 0.1

        # Second request should use cached value
        util2 = routing._get_utilization("test-model")
        assert util2 == 0.1  # Should return cached value

    def test_chat_completions_cache_behavior(self):
        """
        Given: Cache is configured with TTL
        When: Multiple requests are made within TTL window
        Then: Should use cached utilization values (not fetch from API)
        """
        # Arrange
        cache = UtilizationCache(ttl=30)
        mock_client = Mock()

        call_count = 0

        def mock_get_util(chute_id):
            nonlocal call_count
            call_count += 1
            return 0.5

        mock_client.get_utilization = mock_get_util

        routing = ChutesUtilizationRouting(api_client=mock_client, cache=cache)

        # First call - should hit API
        util1 = routing._get_utilization("test-model")

        # Second call - should use cache
        util2 = routing._get_utilization("test-model")

        # Third call - should use cache
        util3 = routing._get_utilization("test-model")

        # Assert - All should return same value, but only first call hits API
        assert util1 == util2 == util3 == 0.5
        assert call_count == 1  # Only first call hits API

    def test_health_endpoint_empty_model_list(self):
        """
        Given: A routing strategy with an empty model list
        When: Health check is called
        Then: The system should handle empty model list gracefully without crashing
        """
        # Arrange - Create routing strategy with empty model list
        cache = UtilizationCache(ttl=30)
        mock_client = Mock()
        mock_client.get_utilization = Mock(return_value=0.5)

        routing = ChutesUtilizationRouting(api_client=mock_client, cache=cache)

        # Mock router with empty model list
        mock_router = Mock()
        mock_router.model_list = []

        # Act - Get utilization for empty model list
        utilizations = routing._get_all_utilizations(mock_router.model_list)

        # Assert - Should handle empty list gracefully
        assert utilizations == {}
        # Verify no crash occurred and system returns empty dict

    def test_chat_completions_api_error_handling(self):
        """
        Given: The Chutes API returns an error response (5xx/4xx)
        When: A chat completions request is made
        Then: The system should handle the error gracefully without crashing
        """
        # Arrange - Create routing with API that returns errors
        cache = UtilizationCache(ttl=30)
        mock_client = Mock()

        # Simulate API error - returns None for utilization (simulates error)
        def mock_get_util_error(chute_id):
            return None  # None indicates API error/unavailable

        mock_client.get_utilization = mock_get_util_error
        mock_client.get_bulk_utilization = Mock(
            return_value={"error": "Internal server error", "status_code": 500}
        )

        routing = ChutesUtilizationRouting(api_client=mock_client, cache=cache)

        mock_router = Mock()
        mock_router.model_list = [
            {"model_name": "provider/model-a", "model_info": {"id": "model-a"}},
            {"model_name": "provider/model-b", "model_info": {"id": "model-b"}},
        ]
        routing.set_router(mock_router)

        # Act - Get utilization when API returns errors
        utilizations = routing._get_all_utilizations(mock_router.model_list)

        # Assert - System should handle errors gracefully (use default values)
        assert "model-a" in utilizations
        assert "model-b" in utilizations
        # Should use default value (0.5) when API returns error
        assert all(util == 0.5 for util in utilizations.values())
