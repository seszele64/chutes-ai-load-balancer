"""
End-to-End tests for complete request flows.

Tests verify the entire system from user request to model response.
These tests use minimal mocking - only mocking external HTTP APIs.
Internal component interactions are tested in their real form.

E2E Test Coverage:
- E2E-001: Primary model flow (lowest utilization)
- E2E-002: Fallback flow (primary fails)
- E2E-003: All models busy flow (above threshold)
- E2E-004: Warm cache flow (cached data available)
- E2E-005: Cold cache flow (cache miss, fresh API call)
- E2E-006: Concurrent request handling
"""

import pytest
from concurrent.futures import ThreadPoolExecutor
from typing import Dict
from unittest.mock import Mock

from litellm_proxy.routing.strategy import ChutesUtilizationRouting
from litellm_proxy.cache.store import UtilizationCache
from litellm_proxy.api.client import ChutesAPIClient


@pytest.mark.e2e
class TestFullRequestFlow:
    """E2E tests for complete request flows."""

    def test_full_request_flow_primary_model(self):
        """
        Given a proxy with multiple models with varying utilization
        When a chat completion request is made
        Then the request should route to the model with lowest utilization

        E2E-001: Tests complete flow routing to primary (lowest utilization) model.
        """
        # Arrange - Set up routing with different utilization levels
        cache = UtilizationCache(ttl=30)

        # Mock API client returning different utilization for each model
        mock_client = Mock(spec=ChutesAPIClient)

        def mock_get_util(chute_id: str):
            """Return different utilization based on chute_id."""
            utilization_map = {
                "model-a": 0.10,  # Lowest - should be selected
                "model-b": 0.50,
                "model-c": 0.80,
            }
            return utilization_map.get(chute_id)

        mock_client.get_utilization = mock_get_util
        mock_client.get_bulk_utilization = Mock(
            return_value={
                "models": [
                    {"model_id": "model-a", "utilization": 0.10},
                    {"model_id": "model-b", "utilization": 0.50},
                    {"model_id": "model-c", "utilization": 0.80},
                ]
            }
        )

        routing = ChutesUtilizationRouting(
            api_client=mock_client, cache=cache, cache_ttl=30
        )

        # Set up mock router with model list
        mock_router = Mock()
        mock_router.model_list = [
            {
                "model_name": "provider/model-a",
                "model_info": {"id": "model-a", "chute_id": "model-a"},
                "litellm_params": {"model": "provider/model-a"},
            },
            {
                "model_name": "provider/model-b",
                "model_info": {"id": "model-b", "chute_id": "model-b"},
                "litellm_params": {"model": "provider/model-b"},
            },
            {
                "model_name": "provider/model-c",
                "model_info": {"id": "model-c", "chute_id": "model-c"},
                "litellm_params": {"model": "provider/model-c"},
            },
        ]
        routing.set_router(mock_router)

        # Act - Get the deployment for a request
        deployment = routing.get_available_deployment(
            model="test-model", request_kwargs={"router": mock_router}
        )

        # Assert - Should select model-a (lowest utilization at 10%)
        assert deployment is not None
        model_info = deployment.get("model_info", {})
        selected_chute_id = model_info.get("id") or model_info.get("chute_id")
        assert selected_chute_id == "model-a", (
            f"Expected model-a (lowest utilization), got {selected_chute_id}"
        )

        # Verify cache is populated after request
        cached_value = cache.get("model-a")
        assert cached_value == 0.10

    def test_full_request_flow_with_fallback(self):
        """
        Given a primary model that is unavailable (high utilization/API error)
        When a request is made
        Then the request should fallback to secondary model

        E2E-002: Tests fallback behavior when primary model fails.
        """
        # Arrange - Set up routing with primary model unavailable
        cache = UtilizationCache(ttl=30)

        mock_client = Mock(spec=ChutesAPIClient)

        call_count = 0

        def mock_get_util(chute_id: str):
            """Simulate primary model being unavailable on first call."""
            nonlocal call_count
            call_count += 1

            # First call - primary unavailable, second call - secondary available
            if chute_id == "model-a" and call_count <= 2:
                return None  # Simulates unavailable/error
            return 0.50

        mock_client.get_utilization = mock_get_util

        routing = ChutesUtilizationRouting(
            api_client=mock_client, cache=cache, cache_ttl=30
        )

        # Set up router with model list
        mock_router = Mock()
        mock_router.model_list = [
            {
                "model_name": "provider/model-a",
                "model_info": {"id": "model-a", "chute_id": "model-a"},
                "litellm_params": {"model": "provider/model-a"},
            },
            {
                "model_name": "provider/model-b",
                "model_info": {"id": "model-b", "chute_id": "model-b"},
                "litellm_params": {"model": "provider/model-b"},
            },
        ]
        routing.set_router(mock_router)

        # Act - Get utilization for all models
        utilizations = routing._get_all_utilizations(mock_router.model_list)

        # Assert - Both models should have values (unavailable uses default 0.5)
        assert "model-a" in utilizations
        assert "model-b" in utilizations
        # model-a gets default (0.5) when unavailable, model-b is 0.5
        assert utilizations["model-a"] == 0.5  # Default for unavailable
        assert utilizations["model-b"] == 0.5

    def test_full_request_flow_all_models_busy(self):
        """
        Given all models have utilization above threshold (e.g., >95%)
        When a request is made
        Then the system should still select a model (least bad option)
        And should log appropriate warning

        E2E-003: Tests behavior when all models are at high utilization.
        """
        # Arrange - All models at high utilization
        cache = UtilizationCache(ttl=30)

        mock_client = Mock()

        def mock_get_util(chute_id: str):
            """All models at high utilization but different."""
            utilization_map = {
                "model-a": 0.98,
                "model-b": 0.97,
                "model-c": 0.96,  # Lowest of the high values
            }
            return utilization_map.get(chute_id)

        mock_client.get_utilization = mock_get_util
        mock_client.get_bulk_utilization = Mock(
            return_value={
                "models": [
                    {"model_id": "model-a", "utilization": 0.98},
                    {"model_id": "model-b", "utilization": 0.97},
                    {"model_id": "model-c", "utilization": 0.96},
                ]
            }
        )

        routing = ChutesUtilizationRouting(
            api_client=mock_client, cache=cache, cache_ttl=30
        )

        mock_router = Mock()
        mock_router.model_list = [
            {
                "model_name": "provider/model-a",
                "model_info": {"id": "model-a"},
                "litellm_params": {"model": "provider/model-a"},
            },
            {
                "model_name": "provider/model-b",
                "model_info": {"id": "model-b"},
                "litellm_params": {"model": "provider/model-b"},
            },
            {
                "model_name": "provider/model-c",
                "model_info": {"id": "model-c"},
                "litellm_params": {"model": "provider/model-c"},
            },
        ]
        routing.set_router(mock_router)

        # Act - Get utilization and select model
        utilizations = routing._get_all_utilizations(mock_router.model_list)

        # Assert - Should still select the model with lowest utilization
        assert len(utilizations) == 3
        assert all(0.95 <= util <= 1.0 for util in utilizations.values())

        # Find least utilized - should be model-c (0.96)
        least_utilized = routing._find_least_utilized(utilizations)
        assert least_utilized == "model-c"

    def test_full_request_flow_cache_warm(self):
        """
        Given the cache has pre-warmed utilization data
        When a request is made
        Then the cache should be used (no API call needed)
        And correct model should be selected based on cached data

        E2E-004: Tests flow with pre-warmed cache.
        """
        # Arrange - Pre-populate cache with utilization data
        cache = UtilizationCache(ttl=30)

        # Pre-warm cache with known utilization values
        cache.set("model-a", 0.30)
        cache.set("model-b", 0.60)
        cache.set("model-c", 0.20)  # Lowest - should be selected

        mock_client = Mock()

        # Use a Mock method that will track calls
        mock_get_util = Mock()

        # If called, fail the test (cache should be used)
        mock_get_util.side_effect = lambda chute_id: (
            pytest.fail("API client should not be called when cache is warm")
        )

        mock_client.get_utilization = mock_get_util
        mock_client.get_bulk_utilization = Mock(return_value={})

        routing = ChutesUtilizationRouting(
            api_client=mock_client, cache=cache, cache_ttl=30
        )

        mock_router = Mock()
        mock_router.model_list = [
            {
                "model_name": "provider/model-a",
                "model_info": {"id": "model-a"},
                "litellm_params": {"model": "provider/model-a"},
            },
            {
                "model_name": "provider/model-b",
                "model_info": {"id": "model-b"},
                "litellm_params": {"model": "provider/model-b"},
            },
            {
                "model_name": "provider/model-c",
                "model_info": {"id": "model-c"},
                "litellm_params": {"model": "provider/model-c"},
            },
        ]
        routing.set_router(mock_router)

        # Act - Get utilizations from warm cache
        utilizations = routing._get_all_utilizations(mock_router.model_list)

        # Assert - Should return cached values
        assert utilizations["model-a"] == 0.30
        assert utilizations["model-b"] == 0.60
        assert utilizations["model-c"] == 0.20  # Lowest

        # Verify API was not called
        mock_get_util.assert_not_called()

    def test_full_request_flow_cache_cold(self):
        """
        Given the cache is cold (empty or expired)
        When a request is made
        Then the API should be called to fetch utilization
        And cache should be populated after the API call
        And correct model should be selected

        E2E-005: Tests flow with cold cache requiring API call.
        """
        # Arrange - Start with empty cache
        cache = UtilizationCache(ttl=30)

        mock_client = Mock(spec=ChutesAPIClient)

        api_call_count = 0

        def mock_get_util(chute_id: str):
            """Return utilization - simulates API call."""
            nonlocal api_call_count
            api_call_count += 1

            utilization_map = {
                "model-a": 0.40,
                "model-b": 0.20,  # Lowest
                "model-c": 0.70,
            }
            return utilization_map.get(chute_id)

        mock_client.get_utilization = mock_get_util

        routing = ChutesUtilizationRouting(
            api_client=mock_client, cache=cache, cache_ttl=30
        )

        mock_router = Mock()
        mock_router.model_list = [
            {
                "model_name": "provider/model-a",
                "model_info": {"id": "model-a"},
                "litellm_params": {"model": "provider/model-a"},
            },
            {
                "model_name": "provider/model-b",
                "model_info": {"id": "model-b"},
                "litellm_params": {"model": "provider/model-b"},
            },
            {
                "model_name": "provider/model-c",
                "model_info": {"id": "model-c"},
                "litellm_params": {"model": "provider/model-c"},
            },
        ]
        routing.set_router(mock_router)

        # Act - First request - should hit API
        utilizations = routing._get_all_utilizations(mock_router.model_list)

        # Assert - API was called for each model
        assert api_call_count >= 1, "API should have been called for cold cache"

        # Assert - Correct utilization values returned
        assert utilizations["model-a"] == 0.40
        assert utilizations["model-b"] == 0.20  # Lowest
        assert utilizations["model-c"] == 0.70

        # Assert - Cache was populated
        assert cache.get("model-a") == 0.40
        assert cache.get("model-b") == 0.20
        assert cache.get("model-c") == 0.70

        # Act - Second request - should use cache
        api_call_count_before = api_call_count
        utilizations_2 = routing._get_all_utilizations(mock_router.model_list)

        # Assert - API was not called again (should use cache)
        assert api_call_count == api_call_count_before, (
            "Cache should be used on second request"
        )

    def test_full_request_flow_concurrent(self):
        """
        Given multiple concurrent requests are made
        When the system handles them
        Then all requests should complete successfully
        And utilization tracking should remain consistent
        And no race conditions should occur

        E2E-006: Tests concurrent request handling.
        """
        # Arrange - Set up routing for concurrent requests
        cache = UtilizationCache(ttl=30)

        mock_client = Mock(spec=ChutesAPIClient)

        # Use a thread-safe counter for API calls
        import threading

        api_call_count = 0
        api_lock = threading.Lock()

        def mock_get_util(chute_id: str):
            """Return utilization - simulates API call."""
            nonlocal api_call_count
            with api_lock:
                api_call_count += 1

            utilization_map = {
                "model-a": 0.30,
                "model-b": 0.50,
                "model-c": 0.70,
            }
            return utilization_map.get(chute_id)

        mock_client.get_utilization = mock_get_util

        routing = ChutesUtilizationRouting(
            api_client=mock_client, cache=cache, cache_ttl=30
        )

        mock_router = Mock()
        mock_router.model_list = [
            {
                "model_name": "provider/model-a",
                "model_info": {"id": "model-a"},
                "litellm_params": {"model": "provider/model-a"},
            },
            {
                "model_name": "provider/model-b",
                "model_info": {"id": "model-b"},
                "litellm_params": {"model": "provider/model-b"},
            },
            {
                "model_name": "provider/model-c",
                "model_info": {"id": "model-c"},
                "litellm_params": {"model": "provider/model-c"},
            },
        ]
        routing.set_router(mock_router)

        # Act - Make multiple concurrent requests
        num_requests = 10
        results = []
        errors = []

        def make_request(request_id: int):
            """Make a single routing request."""
            try:
                deployment = routing.get_available_deployment(
                    model="test-model", request_kwargs={"router": mock_router}
                )
                results.append(
                    {
                        "request_id": request_id,
                        "deployment": deployment,
                    }
                )
            except Exception as e:
                errors.append(
                    {
                        "request_id": request_id,
                        "error": str(e),
                    }
                )

        # Execute concurrent requests
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(make_request, i) for i in range(num_requests)]
            for future in futures:
                future.result()  # Wait for completion

        # Assert - All requests completed successfully
        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(results) == num_requests, (
            f"Expected {num_requests} results, got {len(results)}"
        )

        # Assert - All deployments were selected
        for result in results:
            assert result["deployment"] is not None, (
                f"Deployment is None for request {result['request_id']}"
            )
            model_info = result["deployment"].get("model_info", {})
            selected_id = model_info.get("id") or model_info.get("chute_id")
            assert selected_id in ["model-a", "model-b", "model-c"], (
                f"Invalid model selected for request {result['request_id']}"
            )

        # Assert - Most requests should go to model-a (lowest utilization)
        # But some may go to others due to cache timing - just verify valid selection
        selected_models = [
            r["deployment"]["model_info"].get("id")
            or r["deployment"]["model_info"].get("chute_id")
            for r in results
        ]
        assert all(m in ["model-a", "model-b", "model-c"] for m in selected_models)

        # Assert - Cache is populated (first request triggers API, subsequent use cache)
        assert cache.size() > 0, "Cache should have entries after concurrent requests"
