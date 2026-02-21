"""
Mock routing scenarios for testing.
"""

from typing import Dict, Any, List


def get_low_utilization_scenario() -> List[Dict[str, Any]]:
    """Scenario: One model has significantly lower utilization."""
    return [
        {"model_id": "model-a", "utilization": 10.0, "available": True},
        {"model_id": "model-b", "utilization": 90.0, "available": True},
        {"model_id": "model-c", "utilization": 85.0, "available": True},
    ]


def get_equal_utilization_scenario() -> List[Dict[str, Any]]:
    """Scenario: All models have equal utilization."""
    return [
        {"model_id": "model-a", "utilization": 50.0, "available": True},
        {"model_id": "model-b", "utilization": 50.0, "available": True},
        {"model_id": "model-c", "utilization": 50.0, "available": True},
    ]


def get_unavailable_model_scenario() -> List[Dict[str, Any]]:
    """Scenario: One model is unavailable."""
    return [
        {"model_id": "model-a", "utilization": 30.0, "available": True},
        {"model_id": "model-b", "utilization": 0.0, "available": False},
        {"model_id": "model-c", "utilization": 40.0, "available": True},
    ]


def get_all_unavailable_scenario() -> List[Dict[str, Any]]:
    """Scenario: All models are unavailable."""
    return [
        {"model_id": "model-a", "utilization": 0.0, "available": False},
        {"model_id": "model-b", "utilization": 0.0, "available": False},
        {"model_id": "model-c", "utilization": 0.0, "available": False},
    ]


def get_high_latency_scenario() -> List[Dict[str, Any]]:
    """Scenario: Some models have high latency."""
    return [
        {
            "model_id": "model-a",
            "utilization": 30.0,
            "latency_ms": 100,
            "available": True,
        },
        {
            "model_id": "model-b",
            "utilization": 30.0,
            "latency_ms": 5000,
            "available": True,
        },
        {
            "model_id": "model-c",
            "utilization": 30.0,
            "latency_ms": 150,
            "available": True,
        },
    ]


def get_single_model_scenario() -> List[Dict[str, Any]]:
    """Scenario: Only one model available."""
    return [
        {"model_id": "model-a", "utilization": 50.0, "available": True},
    ]


def get_empty_model_scenario() -> List[Dict[str, Any]]:
    """Scenario: No models available."""
    return []
