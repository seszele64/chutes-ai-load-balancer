"""
Sample model configurations for testing.
"""

from typing import Dict, Any


def get_sample_model_config() -> Dict[str, Any]:
    """Get a sample model configuration."""
    return {
        "model_id": "test-model",
        "name": "Test Model",
        "provider": "chutes",
        "base_url": "https://api.chutes.ai/v1",
    }


def get_multi_model_config() -> list[Dict[str, Any]]:
    """Get configuration for multiple models."""
    return [
        {
            "model_id": "model-a",
            "name": "Model A",
            "provider": "chutes",
            "base_url": "https://api.chutes.ai/v1",
        },
        {
            "model_id": "model-b",
            "name": "Model B",
            "provider": "chutes",
            "base_url": "https://api.chutes.ai/v1",
        },
        {
            "model_id": "model-c",
            "name": "Model C",
            "provider": "chutes",
            "base_url": "https://api.chutes.ai/v1",
        },
    ]


def get_model_with_priority(priority: int) -> Dict[str, Any]:
    """Get model config with specified priority."""
    return {
        "model_id": f"priority-model-{priority}",
        "name": f"Priority Model {priority}",
        "provider": "chutes",
        "priority": priority,
    }
