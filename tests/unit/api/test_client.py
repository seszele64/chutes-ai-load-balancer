"""
Unit tests for API client.

These tests verify the Chutes API client behavior including HTTP requests,
retry logic, timeout handling, and error handling.
"""

import pytest
import requests
from unittest.mock import Mock, patch, MagicMock

# Import the API client and exceptions
from litellm_proxy.api.client import ChutesAPIClient
from litellm_proxy.exceptions import (
    ChutesAPIConnectionError,
    ChutesAPITimeoutError,
    ChutesAPIError,
)


@pytest.mark.unit
def test_api_client_get_request():
    """
    Given: API client with valid credentials
    When: get_utilization() is called
    Then: Returns parsed utilization value from JSON response
    """
    # Arrange
    client = ChutesAPIClient(api_key="test-key", base_url="https://api.chutes.ai")

    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = [
        {"chute_id": "chute-123", "utilization_current": 0.45}
    ]
    mock_response.raise_for_status = Mock()

    with patch.object(client.session, "get", return_value=mock_response):
        # Act
        result = client.get_utilization("chute-123")

    # Assert
    assert result == 0.45


@pytest.mark.unit
def test_api_client_retry_on_5xx():
    """
    Given: API returns 503 Service Unavailable
    When: get_utilization() is called
    Then: Raises ChutesAPIConnectionError (client doesn't auto-retry)
    """
    # Arrange
    client = ChutesAPIClient(api_key="test-key", base_url="https://api.chutes.ai")

    mock_response = Mock()
    mock_response.status_code = 503
    mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
        "503 Server Error"
    )

    with patch.object(client.session, "get", return_value=mock_response):
        # Act & Assert
        with pytest.raises(ChutesAPIConnectionError):
            client.get_utilization("chute-123")


@pytest.mark.unit
def test_api_client_no_retry_on_4xx():
    """
    Given: API returns 400 Bad Request
    When: get_utilization() is called
    Then: Raises ChutesAPIConnectionError (no retry for client errors)
    """
    # Arrange
    client = ChutesAPIClient(api_key="test-key", base_url="https://api.chutes.ai")

    mock_response = Mock()
    mock_response.status_code = 400
    mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
        "400 Bad Request"
    )

    with patch.object(client.session, "get", return_value=mock_response):
        # Act & Assert
        with pytest.raises(ChutesAPIConnectionError):
            client.get_utilization("chute-123")


@pytest.mark.unit
def test_api_client_timeout():
    """
    Given: API request times out
    When: get_utilization() is called
    Then: Raises ChutesAPITimeoutError
    """
    # Arrange
    client = ChutesAPIClient(
        api_key="test-key", base_url="https://api.chutes.ai", timeout=1
    )

    with patch.object(client.session, "get", side_effect=requests.exceptions.Timeout()):
        # Act & Assert
        with pytest.raises(ChutesAPITimeoutError):
            client.get_utilization("chute-123")


@pytest.mark.unit
def test_api_client_connection_error():
    """
    Given: Connection to API fails
    When: get_utilization() is called
    Then: Raises ChutesAPIConnectionError
    """
    # Arrange
    client = ChutesAPIClient(api_key="test-key", base_url="https://api.chutes.ai")

    with patch.object(
        client.session, "get", side_effect=requests.exceptions.ConnectionError()
    ):
        # Act & Assert
        with pytest.raises(ChutesAPIConnectionError):
            client.get_utilization("chute-123")


@pytest.mark.unit
def test_api_client_rate_limit_handling():
    """
    Given: API returns 429 with Retry-After header
    When: get_utilization() is called
    Then: Raises ChutesAPIConnectionError (rate limiting not auto-handled)
    """
    # Arrange
    client = ChutesAPIClient(api_key="test-key", base_url="https://api.chutes.ai")

    mock_response = Mock()
    mock_response.status_code = 429
    mock_response.headers = {"Retry-After": "60"}
    mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
        "429 Rate Limited"
    )

    with patch.object(client.session, "get", return_value=mock_response):
        # Act & Assert - current implementation raises on HTTP error
        with pytest.raises(ChutesAPIConnectionError):
            client.get_utilization("chute-123")
