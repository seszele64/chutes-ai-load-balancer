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


# ============================================================================
# Phase 1: Additional API Client Tests (TC-1 through TC-14)
# ============================================================================


@pytest.mark.unit
def test_api_client_get_utilization_without_api_key():
    """
    TC-1: Given: API client without API key
    When: get_utilization() is called
    Then: Returns None without making any API call
    """
    # Arrange
    client = ChutesAPIClient(api_key=None, base_url="https://api.chutes.ai")

    # Act
    result = client.get_utilization("chute-123")

    # Assert
    assert result is None


@pytest.mark.unit
def test_api_client_get_utilization_key_error_parsing():
    """
    TC-2: Given: API returns response with invalid data type (non-numeric string)
    When: get_utilization() is called
    Then: Raises ChutesAPIError
    """
    # Arrange
    client = ChutesAPIClient(api_key="test-key", base_url="https://api.chutes.ai")

    mock_response = Mock()
    mock_response.status_code = 200
    # Return a dict with wrong type values to trigger ValueError during conversion
    mock_response.json.return_value = {
        "chutes": {"chute-123": {"utilization": "not-a-number"}}
    }
    mock_response.raise_for_status = Mock()

    with patch.object(client.session, "get", return_value=mock_response):
        # Act & Assert
        with pytest.raises(ChutesAPIError):
            client.get_utilization("chute-123")


@pytest.mark.unit
def test_api_client_get_utilization_value_error_parsing():
    """
    TC-3: Given: API returns response with invalid data type
    When: get_utilization() is called
    Then: Raises ChutesAPIError (ValueError during parsing)
    """
    # Arrange
    client = ChutesAPIClient(api_key="test-key", base_url="https://api.chutes.ai")

    mock_response = Mock()
    mock_response.status_code = 200
    # Return a dict with wrong type values to trigger ValueError
    mock_response.json.return_value = {
        "chutes": {"chute-123": {"utilization": "not-a-number"}}
    }
    mock_response.raise_for_status = Mock()

    with patch.object(client.session, "get", return_value=mock_response):
        # Act & Assert
        with pytest.raises(ChutesAPIError):
            client.get_utilization("chute-123")


@pytest.mark.unit
def test_api_client_get_bulk_utilization_success():
    """
    TC-4: Given: API client with valid credentials
    When: get_bulk_utilization() is called
    Then: Returns dictionary of chute_id to utilization
    """
    # Arrange
    client = ChutesAPIClient(api_key="test-key", base_url="https://api.chutes.ai")

    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = [
        {"chute_id": "chute-123", "utilization_current": 0.45},
        {"chute_id": "chute-456", "utilization_current": 0.75},
    ]
    mock_response.raise_for_status = Mock()

    with patch.object(client.session, "get", return_value=mock_response):
        # Act
        result = client.get_bulk_utilization()

    # Assert
    assert result == {"chute-123": 0.45, "chute-456": 0.75}


@pytest.mark.unit
def test_api_client_get_bulk_utilization_without_api_key():
    """
    TC-5: Given: API client without API key
    When: get_bulk_utilization() is called
    Then: Returns empty dictionary
    """
    # Arrange
    client = ChutesAPIClient(api_key=None, base_url="https://api.chutes.ai")

    # Act
    result = client.get_bulk_utilization()

    # Assert
    assert result == {}


@pytest.mark.unit
def test_api_client_get_bulk_utilization_timeout():
    """
    TC-6: Given: API request times out
    When: get_bulk_utilization() is called
    Then: Raises ChutesAPITimeoutError
    """
    # Arrange
    client = ChutesAPIClient(
        api_key="test-key", base_url="https://api.chutes.ai", timeout=1
    )

    with patch.object(client.session, "get", side_effect=requests.exceptions.Timeout()):
        # Act & Assert
        with pytest.raises(ChutesAPITimeoutError):
            client.get_bulk_utilization()


@pytest.mark.unit
def test_api_client_get_bulk_utilization_connection_error():
    """
    TC-7: Given: Connection to API fails
    When: get_bulk_utilization() is called
    Then: Raises ChutesAPIConnectionError
    """
    # Arrange
    client = ChutesAPIClient(api_key="test-key", base_url="https://api.chutes.ai")

    with patch.object(
        client.session, "get", side_effect=requests.exceptions.ConnectionError()
    ):
        # Act & Assert
        with pytest.raises(ChutesAPIConnectionError):
            client.get_bulk_utilization()


@pytest.mark.unit
def test_api_client_get_bulk_utilization_parsing_error():
    """
    TC-8: Given: API returns unparseable response
    When: get_bulk_utilization() is called
    Then: Raises ChutesAPIError
    """
    # Arrange
    client = ChutesAPIClient(api_key="test-key", base_url="https://api.chutes.ai")

    mock_response = Mock()
    mock_response.status_code = 200
    # Return invalid data to trigger parsing error
    mock_response.json.side_effect = ValueError("Invalid JSON structure")
    mock_response.raise_for_status = Mock()

    with patch.object(client.session, "get", return_value=mock_response):
        # Act & Assert
        with pytest.raises(ChutesAPIError):
            client.get_bulk_utilization()


@pytest.mark.unit
def test_parse_utilization_response_dict_format():
    """
    TC-9: Given: API response as dictionary format
    When: _parse_utilization_response() is called
    Then: Returns utilization value from dict
    """
    # Arrange
    client = ChutesAPIClient(api_key="test-key", base_url="https://api.chutes.ai")

    # Test dict with 'utilization' field
    data = {"chutes": {"chute-123": {"utilization": 0.65}}}

    # Act
    result = client._parse_utilization_response(data, "chute-123")

    # Assert
    assert result == 0.65


@pytest.mark.unit
def test_parse_utilization_response_name_matching_fallback():
    """
    TC-10: Given: API response without chute_id match
    When: _parse_utilization_response() is called
    Then: Falls back to name matching

    The normalization removes "chute_" prefix and replaces remaining underscores with dashes.
    So "chute_123" becomes "123" after normalization.
    """
    # Arrange
    client = ChutesAPIClient(api_key="test-key", base_url="https://api.chutes.ai")

    # chute_id = "chute_123" normalizes to "123"
    # name = "123" normalizes to "123"
    # "123" in "123" = True
    data = [{"name": "123", "utilization_current": 0.55}]

    # Act
    result = client._parse_utilization_response(data, "chute_123")

    # Assert
    assert result == 0.55


@pytest.mark.unit
def test_parse_utilization_response_not_found():
    """
    TC-11: Given: API response without matching chute
    When: _parse_utilization_response() is called
    Then: Returns None (no fallback value in parsing function)
    """
    # Arrange
    client = ChutesAPIClient(api_key="test-key", base_url="https://api.chutes.ai")

    # Empty list - no matching chute
    data = []

    # Act
    result = client._parse_utilization_response(data, "chute-123")

    # Assert
    assert result is None


@pytest.mark.unit
def test_parse_bulk_utilization_list_response():
    """
    TC-12: Given: API response as list format
    When: _parse_bulk_utilization() is called
    Then: Returns dictionary of chute_id to utilization
    """
    # Arrange
    client = ChutesAPIClient(api_key="test-key", base_url="https://api.chutes.ai")

    data = [
        {"chute_id": "chute-1", "utilization_current": 0.3},
        {"chute_id": "chute-2", "utilization_current": 0.7},
    ]

    # Act
    result = client._parse_bulk_utilization(data)

    # Assert
    assert result == {"chute-1": 0.3, "chute-2": 0.7}


@pytest.mark.unit
def test_parse_bulk_utilization_dict_data_format():
    """
    TC-13: Given: API response as dict with 'data' key
    When: _parse_bulk_utilization() is called
    Then: Returns dictionary of chute_id to utilization
    """
    # Arrange
    client = ChutesAPIClient(api_key="test-key", base_url="https://api.chutes.ai")

    data = {
        "data": [
            {"chute_id": "chute-a", "utilization_current": 0.4},
            {"chute_id": "chute-b", "utilization_current": 0.6},
        ]
    }

    # Act
    result = client._parse_bulk_utilization(data)

    # Assert
    assert result == {"chute-a": 0.4, "chute-b": 0.6}


@pytest.mark.unit
def test_api_client_close_closes_session():
    """
    TC-14: Given: API client with active session
    When: close() is called
    Then: Session is closed and set to None
    """
    # Arrange
    client = ChutesAPIClient(api_key="test-key", base_url="https://api.chutes.ai")
    # Create a session by accessing it
    _ = client.session
    assert client._session is not None

    # Mock the session's close method
    mock_close = Mock()
    client._session.close = mock_close

    # Act
    client.close()

    # Assert
    mock_close.assert_called_once()
    assert client._session is None
