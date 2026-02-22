"""
Mock API responses for testing.
"""

from typing import Dict, Any, List
from unittest.mock import Mock


def get_utilization_response(
    model_id: str = "test-model", utilization: float = 50.0
) -> Dict[str, Any]:
    """Get mock utilization response."""
    return {
        "model_id": model_id,
        "utilization": utilization,
        "latency_ms": 100,
        "timestamp": "2024-01-01T00:00:00Z",
    }


def get_bulk_utilization_response() -> Dict[str, Any]:
    """Get mock bulk utilization response."""
    return {
        "models": [
            {"model_id": "model-a", "utilization": 25.0, "latency_ms": 100},
            {"model_id": "model-b", "utilization": 75.0, "latency_ms": 200},
            {"model_id": "model-c", "utilization": 50.0, "latency_ms": 150},
        ]
    }


def get_chat_completion_response() -> Dict[str, Any]:
    """Get mock chat completion response."""
    return {
        "id": "chatcmpl-123",
        "object": "chat.completion",
        "created": 1677652288,
        "model": "test-model",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "Hello! How can I help you today?",
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 20,
            "total_tokens": 30,
        },
    }


def get_error_response(status_code: int, message: str) -> Dict[str, Any]:
    """Get mock error response."""
    return {
        "error": {
            "message": message,
            "type": "invalid_request_error",
            "code": status_code,
        }
    }


def create_mock_response(
    status_code: int = 200, json_data: Dict[str, Any] = None
) -> Mock:
    """Create a mock HTTP response."""
    response = Mock()
    response.status_code = status_code
    if json_data:
        response.json.return_value = json_data
    response.raise_for_status = (
        Mock()
        if status_code < 400
        else Mock(side_effect=Exception(f"HTTP {status_code}"))
    )
    return response
