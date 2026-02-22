"""
Shared pytest fixtures for all test modules.
"""

import sys
from pathlib import Path
from typing import Any, Dict, Generator

import pytest
import yaml
from unittest.mock import Mock

# Add src to path for imports
src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from litellm_proxy.cache.store import UtilizationCache
from litellm_proxy.api.client import ChutesAPIClient
from litellm_proxy.routing.strategy import ChutesUtilizationRouting
from litellm_proxy.config.loader import ConfigLoader


@pytest.fixture
def temp_config_dir(tmp_path: Path) -> Path:
    """Create temporary directory for config files."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    return config_dir


@pytest.fixture
def sample_yaml_config(temp_config_dir: Path) -> Path:
    """Create sample YAML config file."""
    config = {
        "models": ["model-a", "model-b", "model-c"],
        "routing_strategy": "chutes_utilization",
        "cache_ttl": 60,
        "timeout": 30,
    }
    config_file = temp_config_dir / "config.yaml"
    config_file.write_text(yaml.dump(config))
    return config_file


@pytest.fixture
def mock_utilization_data() -> Dict[str, Any]:
    """Sample utilization data from Chutes API."""
    return {
        "models": [
            {"model_id": "model-a", "utilization": 25.0, "latency_ms": 100},
            {"model_id": "model-b", "utilization": 75.0, "latency_ms": 200},
            {"model_id": "model-c", "utilization": 50.0, "latency_ms": 150},
        ]
    }


@pytest.fixture
def mock_api_client(mock_utilization_data: Dict[str, Any]) -> Mock:
    """Mock Chutes API client."""
    client = Mock(spec=ChutesAPIClient)
    client.get_utilization.return_value = 25.0
    client.get_bulk_utilization.return_value = mock_utilization_data
    return client


@pytest.fixture
def utilization_cache() -> UtilizationCache:
    """Create UtilizationCache with default TTL."""
    return UtilizationCache(ttl=30)


@pytest.fixture
def routing_strategy(
    mock_api_client: Mock, utilization_cache: UtilizationCache
) -> ChutesUtilizationRouting:
    """Create ChutesUtilizationRouting with mocked dependencies."""
    return ChutesUtilizationRouting(api_client=mock_api_client, cache=utilization_cache)


@pytest.fixture
def cli_args_minimal() -> Dict[str, Any]:
    """Minimal CLI arguments for testing."""
    return {
        "models": ["test-model"],
        "port": 8000,
    }


@pytest.fixture
def cli_args_full() -> Dict[str, Any]:
    """Full CLI arguments for testing."""
    return {
        "models": ["model-1", "model-2", "model-3"],
        "port": 8080,
        "config": "/tmp/test-config.yaml",
        "routing_strategy": "chutes_utilization",
        "cache_ttl": 120,
    }


@pytest.fixture
def env_vars_with_models(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set environment variables for testing.

    Uses monkeypatch for proper cleanup after test.
    """
    monkeypatch.setenv("LITELLM_MODELS", "env-model-1,env-model-2")
    monkeypatch.setenv("LITELLM_ROUTING_STRATEGY", "chutes_utilization")
    monkeypatch.setenv("LITELLM_CACHE_TTL", "60")


@pytest.fixture
def sample_config() -> Dict[str, Any]:
    """Sample configuration dictionary."""
    return {
        "models": ["model-a", "model-b", "model-c"],
        "routing_strategy": "chutes_utilization",
        "cache_ttl": 60,
        "timeout": 30,
        "api_base_url": "https://api.chutes.ai",
    }


@pytest.fixture
def mock_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set up mock environment variables."""
    monkeypatch.setenv("LITELLM_MODELS", "test-model-1,test-model-2")
    monkeypatch.setenv("LITELLM_CACHE_TTL", "60")
    monkeypatch.setenv("LITELLM_TIMEOUT", "30")


@pytest.fixture
def temp_config_file(tmp_path: Path, sample_config: Dict[str, Any]) -> Path:
    """Create temporary YAML config file."""
    config_file = tmp_path / "test_config.yaml"
    config_file.write_text(yaml.dump(sample_config))
    return config_file


@pytest.fixture
def mock_model() -> Dict[str, Any]:
    """Mock model configuration."""
    return {
        "model_id": "test-model",
        "name": "Test Model",
        "provider": "chutes",
        "base_url": "https://api.chutes.ai/v1",
    }


@pytest.fixture
def model_list() -> list[Dict[str, Any]]:
    """List of mock model configurations."""
    return [
        {"model_id": "model-a", "name": "Model A", "provider": "chutes"},
        {"model_id": "model-b", "name": "Model B", "provider": "chutes"},
        {"model_id": "model-c", "name": "Model C", "provider": "chutes"},
    ]


@pytest.fixture
def mock_http_response() -> Mock:
    """Mock HTTP response object."""
    response = Mock()
    response.status_code = 200
    response.json.return_value = {"status": "ok"}
    response.raise_for_status = Mock()
    return response


@pytest.fixture
def mock_http_client() -> Mock:
    """Mock HTTP client."""
    client = Mock()
    client.get = Mock()
    client.post = Mock()
    client.request = Mock()
    return client


@pytest.fixture
def cache_config() -> Dict[str, Any]:
    """Cache configuration for testing."""
    return {
        "ttl": 30,
        "max_size": 100,
        "eviction_policy": "lru",
    }


@pytest.fixture(autouse=True)
def reset_singletons() -> Generator[None, None, None]:
    """Reset any singleton state between tests."""
    yield
    # Add any singleton reset logic here if needed


@pytest.fixture(autouse=True)
def reset_module_state() -> Generator[None, None, None]:
    """Reset module-level state between tests."""
    yield
    # Clean up any module-level state
