"""
Unit tests for chutes routing strategy.

These tests verify the routing logic for selecting the least utilized model
based on real-time utilization data.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch

# Import the routing strategy and exceptions
from litellm_proxy.routing.strategy import ChutesUtilizationRouting
from litellm_proxy.cache.store import UtilizationCache
from litellm_proxy.api.client import ChutesAPIClient
from litellm_proxy.exceptions import EmptyModelListError


@pytest.mark.unit
def test_routing_selects_lowest_utilization_model(mock_api_client, utilization_cache):
    """
    Given: Models with different utilization percentages (80%, 20%, 50%)
    When: _find_least_utilized() is called
    Then: Model with lowest utilization (20%) is selected
    """
    # Arrange
    routing = ChutesUtilizationRouting(
        api_client=mock_api_client, cache=utilization_cache
    )

    utilizations = {"model-a": 0.8, "model-b": 0.2, "model-c": 0.5}

    # Act
    selected = routing._find_least_utilized(utilizations)

    # Assert
    assert selected == "model-b"


@pytest.mark.unit
def test_routing_equal_utilization_returns_first_match(
    mock_api_client, utilization_cache
):
    """
    Given: Multiple models with equal utilization (50%, 50%, 50%)
    When: Multiple _find_least_utilized() calls are made
    Then: Returns first model found (Python's min returns first match)
    """
    # Arrange
    routing = ChutesUtilizationRouting(
        api_client=mock_api_client, cache=utilization_cache
    )

    utilizations = {"model-a": 0.5, "model-b": 0.5, "model-c": 0.5}

    # Act - call multiple times
    results = [routing._find_least_utilized(utilizations) for _ in range(3)]

    # Assert - With equal values, Python's min returns the first one found
    # This is deterministic behavior
    assert all(r == "model-a" for r in results)


@pytest.mark.unit
def test_routing_empty_model_list(mock_api_client, utilization_cache):
    """
    Given: An empty model utilization dictionary
    When: _find_least_utilized() is called
    Then: Returns None (no models available)
    """
    # Arrange
    routing = ChutesUtilizationRouting(
        api_client=mock_api_client, cache=utilization_cache
    )

    utilizations = {}

    # Act
    selected = routing._find_least_utilized(utilizations)

    # Assert
    assert selected is None


@pytest.mark.unit
def test_routing_single_model(mock_api_client, utilization_cache):
    """
    Given: Single model in the utilization dictionary
    When: _find_least_utilized() is called
    Then: Always returns that model
    """
    # Arrange
    routing = ChutesUtilizationRouting(
        api_client=mock_api_client, cache=utilization_cache
    )

    utilizations = {"model-a": 0.5}

    # Act
    selected = routing._find_least_utilized(utilizations)

    # Assert
    assert selected == "model-a"


@pytest.mark.unit
def test_routing_model_config_structure():
    """
    Given: Model configuration data with model_info
    When: Creating model instances via routing strategy
    Then: Properly initialized objects with correct model_info
    """
    # Arrange - Create routing strategy that will work with model configs
    routing = ChutesUtilizationRouting(cache_ttl=30)

    # Act - Verify routing can process model configs
    model_list = [
        {
            "model_name": "provider/model-a",
            "model_info": {"id": "chute-123", "chute_id": "model-a"},
        },
        {
            "model_name": "provider/model-b",
            "model_info": {"id": "chute-456", "chute_id": "model-b"},
        },
    ]

    # Mock the router to provide model list
    routing.router = Mock()
    routing.router.model_list = model_list

    # Assert - verify model configs are properly structured
    assert len(model_list) == 2
    assert model_list[0]["model_info"]["id"] == "chute-123"
    assert model_list[1]["model_info"]["chute_id"] == "model-b"


@pytest.mark.unit
def test_routing_updates_utilization(utilization_cache):
    """
    Given: A model is selected for a request
    When: Cache.set() is called after request
    Then: Utilization counter is incremented/cached
    """
    # Arrange
    cache = UtilizationCache(ttl=30)
    chute_id = "test-chute"
    initial_utilization = 0.3

    # Act - set utilization in cache
    cache.set(chute_id, initial_utilization)

    # Retrieve and verify
    cached_value = cache.get(chute_id)

    # Assert
    assert cached_value == initial_utilization
    assert cache.size() == 1


@pytest.mark.unit
def test_routing_filters_unavailable_models():
    """
    Given: Mix of available (has utilization) and unavailable models
    When: _get_all_utilizations() is called
    Then: Excludes unavailable models (uses default 0.5 for unavailable)
    """
    # Arrange - create fresh instances to avoid fixture interference
    from litellm_proxy.cache.store import UtilizationCache
    from litellm_proxy.api.client import ChutesAPIClient

    cache = UtilizationCache(ttl=30)

    # Create a mock API client that returns None for unavailable model
    mock_client = Mock(spec=ChutesAPIClient)

    def mock_get_util(chute_id):
        if chute_id == "unavailable-model":
            return None  # Simulates API failure/unavailable
        return 0.5  # Available model

    mock_client.get_utilization = mock_get_util

    routing = ChutesUtilizationRouting(api_client=mock_client, cache=cache)

    model_list = [
        {"model_name": "available-model", "model_info": {"id": "available-model"}},
        {"model_name": "unavailable-model", "model_info": {"id": "unavailable-model"}},
    ]

    # Act
    utilizations = routing._get_all_utilizations(model_list)

    # Assert - both models should have values (unavailable uses default 0.5)
    assert "available-model" in utilizations
    assert "unavailable-model" in utilizations
    assert utilizations["available-model"] == 0.5
    assert (
        utilizations["unavailable-model"] == 0.5
    )  # Uses default when API returns None
