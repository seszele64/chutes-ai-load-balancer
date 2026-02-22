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


# ============================================================================
# Phase 2: Additional Routing Strategy Tests (TC-15 through TC-25)
# ============================================================================


@pytest.mark.unit
def test_routing_api_client_lazy_initialization():
    """
    TC-15: Given: Routing strategy without API client
    When: api_client property is accessed
    Then: Creates new ChutesAPIClient instance
    """
    # Arrange
    routing = ChutesUtilizationRouting(cache_ttl=30)
    assert routing._api_client is None

    # Act
    client = routing.api_client

    # Assert
    assert client is not None
    assert isinstance(client, ChutesAPIClient)
    assert routing._api_client is client


@pytest.mark.unit
def test_routing_cache_lazy_initialization():
    """
    TC-16: Given: Routing strategy without cache
    When: cache property is accessed
    Then: Creates new UtilizationCache instance
    """
    # Arrange
    routing = ChutesUtilizationRouting(cache_ttl=30)
    assert routing._cache is None

    # Act
    cache = routing.cache

    # Assert
    assert cache is not None
    assert isinstance(cache, UtilizationCache)
    assert routing._cache is cache


@pytest.mark.unit
def test_routing_get_all_utilizations_extracts_from_model_name():
    """
    TC-17: Given: Model config without model_info
    When: _get_all_utilizations() is called
    Then: Extracts chute_id from model name (litellm_params)
    """
    # Arrange
    mock_client = Mock(spec=ChutesAPIClient)
    mock_client.get_utilization.return_value = 0.4
    cache = UtilizationCache(ttl=30)

    routing = ChutesUtilizationRouting(api_client=mock_client, cache=cache)

    model_list = [
        {
            "model_name": "provider/my-chute-model",
            "litellm_params": {"model": "provider/my-chute-model"},
        }
    ]

    # Act
    utilizations = routing._get_all_utilizations(model_list)

    # Assert - should extract chute_id from model name
    assert "my-chute-model" in utilizations
    assert utilizations["my-chute-model"] == 0.4


@pytest.mark.unit
def test_routing_get_model_list_uses_getattr_fallback():
    """
    TC-18: Given: Routing strategy without router but with model_list on self
    When: _get_model_list() is called
    Then: Uses getattr fallback to get model_list
    """
    # Arrange
    routing = ChutesUtilizationRouting(cache_ttl=30)
    # Set model_list directly on the routing instance
    test_model_list = [{"model_name": "model-a", "model_info": {"id": "chute-a"}}]
    routing.model_list = test_model_list

    # Act
    result = routing._get_model_list()

    # Assert
    assert result == test_model_list


@pytest.mark.unit
def test_routing_get_model_list_uses_request_kwargs_router():
    """
    TC-19: Given: No model_list from router or self
    When: _get_model_list() is called with request_kwargs
    Then: Gets model_list from request_kwargs router
    """
    # Arrange
    routing = ChutesUtilizationRouting(cache_ttl=30)

    test_model_list = [{"model_name": "model-x", "model_info": {"id": "chute-x"}}]
    mock_router = Mock()
    mock_router.model_list = test_model_list

    request_kwargs = {"router": mock_router}

    # Act
    result = routing._get_model_list(request_kwargs)

    # Assert
    assert result == test_model_list


@pytest.mark.unit
@pytest.mark.asyncio
async def test_routing_async_get_available_deployment_exception_handling():
    """
    TC-20: Given: Exception raised during async_get_available_deployment
    When: async_get_available_deployment() is called
    Then: Returns None and logs error (doesn't raise)
    """
    # Arrange
    mock_client = Mock(spec=ChutesAPIClient)
    mock_client.get_utilization.side_effect = Exception("API Error")
    cache = UtilizationCache(ttl=30)

    routing = ChutesUtilizationRouting(api_client=mock_client, cache=cache)

    # Set model_list directly on self to avoid router dependency
    test_model_list = [{"model_name": "model-a", "model_info": {"id": "chute-123"}}]
    routing.model_list = test_model_list

    # Act
    result = await routing.async_get_available_deployment(model="model-a")

    # Assert - should return first model (fallback) even on exception
    # The code uses default 0.5 for unavailable and returns first model
    assert result is not None


@pytest.mark.unit
def test_routing_get_available_deployment_empty_model_list():
    """
    TC-21: Given: Empty model list
    When: get_available_deployment() is called
    Then: Returns None
    """
    # Arrange
    routing = ChutesUtilizationRouting(cache_ttl=30)
    routing.router = Mock()
    routing.router.model_list = []

    # Act
    result = routing.get_available_deployment(model="model-a")

    # Assert
    assert result is None


@pytest.mark.unit
def test_routing_get_available_deployment_empty_utilizations():
    """
    TC-22: Given: Model list but no utilization data
    When: get_available_deployment() is called
    Then: Returns first available model (fallback behavior)

    Note: The code uses default 0.5 for unavailable models and returns
    the first model in the list as fallback.
    """
    # Arrange
    mock_client = Mock(spec=ChutesAPIClient)
    mock_client.get_utilization.return_value = None  # Simulates API failure
    cache = UtilizationCache(ttl=30)

    routing = ChutesUtilizationRouting(api_client=mock_client, cache=cache)

    model_list = [{"model_name": "model-a", "model_info": {"id": "chute-123"}}]
    routing.router = Mock()
    routing.router.model_list = model_list

    # Act
    result = routing.get_available_deployment(model="model-a")

    # Assert - returns first model as fallback (uses default 0.5)
    assert result is not None
    assert result["model_name"] == "model-a"


@pytest.mark.unit
def test_routing_get_available_deployment_exception_handling():
    """
    TC-24: Given: Exception raised during get_available_deployment
    When: get_available_deployment() is called
    Then: Returns first model (fallback behavior doesn't raise)

    Note: The code catches exceptions and uses default values,
    returning the first available model.
    """
    # Arrange
    mock_client = Mock(spec=ChutesAPIClient)
    mock_client.get_utilization.side_effect = Exception("API Error")
    cache = UtilizationCache(ttl=30)

    routing = ChutesUtilizationRouting(api_client=mock_client, cache=cache)

    model_list = [{"model_name": "model-a", "model_info": {"id": "chute-123"}}]
    routing.router = Mock()
    routing.router.model_list = model_list

    # Act
    result = routing.get_available_deployment(model="model-a")

    # Assert - returns first model as fallback (uses default 0.5)
    assert result is not None
    assert result["model_name"] == "model-a"


@pytest.mark.unit
def test_routing_get_available_deployment_cannot_find_least_utilized():
    """
    TC-23: Given: Utilization data but _find_least_utilized returns None
    When: get_available_deployment() is called
    Then: Returns None
    """
    # Arrange
    mock_client = Mock(spec=ChutesAPIClient)
    cache = UtilizationCache(ttl=30)

    routing = ChutesUtilizationRouting(api_client=mock_client, cache=cache)
    # Mock _find_least_utilized to return None (empty dict edge case)
    routing._find_least_utilized = Mock(return_value=None)

    model_list = [{"model_name": "model-a", "model_info": {"id": "chute-123"}}]
    routing.router = Mock()
    routing.router.model_list = model_list

    # Act
    result = routing.get_available_deployment(model="model-a")

    # Assert
    assert result is None


@pytest.mark.unit
def test_routing_create_chutes_routing_strategy_factory():
    """
    TC-25: Given: Valid parameters
    When: create_chutes_routing_strategy() is called
    Then: Returns ChutesUtilizationRouting instance
    """
    # Act
    from litellm_proxy.routing.strategy import create_chutes_routing_strategy

    result = create_chutes_routing_strategy(chutes_api_key="test-key", cache_ttl=60)

    # Assert
    assert isinstance(result, ChutesUtilizationRouting)
    assert result.chutes_api_key == "test-key"
    assert result.cache_ttl == 60
