# DESIGN: VDD Test Criteria Implementation

## Overview

This document provides the technical design for implementing the Verification-Driven Development (VDD) test criteria for the chutes-load-balancer system. It covers test directory structure, pytest configuration, fixtures, mocking strategies, and test execution patterns.

## Architecture

### Test Directory Structure

```
chutes-load-balancer/
├── tests/
│   ├── __init__.py
│   ├── conftest.py                 # Shared fixtures
│   ├── unit/
│   │   ├── __init__.py
│   │   ├── test_routing.py         # 7 tests
│   │   ├── test_config.py          # 10 tests
│   │   ├── test_cache.py           # 8 tests
│   │   └── test_api_client.py      # 7 tests
│   ├── integration/
│   │   ├── __init__.py
│   │   ├── test_endpoints.py       # 8 tests
│   │   ├── test_config_loading.py  # 5 tests
│   │   └── test_model_switching.py # 3 tests
│   └── e2e/
│       ├── __init__.py
│       └── test_full_flows.py      # 6 tests
├── scripts/
│   ├── verify_package_structure.py
│   ├── verify_no_hardcoded_models.py
│   ├── verify_shell_scripts_deprecated.py
│   └── verify_python_equivalence.py
└── pyproject.toml                  # pytest configuration
```

## Pytest Configuration

### pyproject.toml Settings

```toml
[tool.pytest.ini_options]
minversion = "7.0"
testpaths = ["tests"]
python_files = ["test_*.py", "*_test.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]

# Output options
addopts = [
    "-v",
    "--strict-markers",
    "--tb=short",
    "--showlocals",
]

# Markers for categorizing tests
markers = [
    "unit: Unit tests (fast, isolated)",
    "integration: Integration tests (component interaction)",
    "e2e: End-to-end tests (full workflow)",
    "slow: Tests that take > 1 second",
    "network: Tests that make network calls",
    "mock: Tests that use mocks",
]

# Coverage options
[tool.coverage.run]
source = ["."]
omit = [
    "tests/*",
    "*/test_*.py",
    "*/__pycache__/*",
    "*/.venv/*",
    "scripts/*",
]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "raise AssertionError",
    "raise NotImplementedError",
    "if __name__ == .__main__.:",
    "if TYPE_CHECKING:",
    "@abstractmethod",
]

# Coverage thresholds
[tool.coverage.html]
directory = "htmlcov"

[tool.coverage.report]
precision = 2
show_missing = true
skip_covered = false
```

## Custom Exception Hierarchy

All custom exceptions are defined in `src/litellm_proxy/exceptions.py`:

```
ChutesRoutingError (Exception)
├── EmptyModelListError
├── ConfigurationError
├── ModelUnavailableError
└── RateLimitError

ChutesAPIError (Exception)
├── ChutesAPIConnectionError
└── ChutesAPITimeoutError
```

These exceptions are used throughout the test suite to verify error handling.

## Test Fixtures (conftest.py)

### Shared Fixtures

```python
"""
Shared pytest fixtures for chutes-load-balancer tests.
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, MagicMock, AsyncMock
from typing import Dict, Any, List

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


# ============================================================================
# Configuration Fixtures
# ============================================================================

@pytest.fixture
def sample_config() -> Dict[str, Any]:
    """Sample configuration for testing."""
    return {
        "host": "0.0.0.0",
        "port": 4000,
        "log_level": "INFO",
        "models": [
            {"name": "model-a", "utilization": 50},
            {"name": "model-b", "utilization": 30},
            {"name": "model-c", "utilization": 20},
        ],
        "routing": {
            "strategy": "least_utilized",
            "fallback_enabled": True,
        },
    }


@pytest.fixture
def mock_env_vars(monkeypatch):
    """Set up mock environment variables."""
    env_vars = {
        "LB_HOST": "127.0.0.1",
        "LB_PORT": "5000",
        "LB_LOG_LEVEL": "DEBUG",
    }
    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)
    return env_vars


@pytest.fixture
def temp_config_file(tmp_path, sample_config):
    """Create a temporary config file."""
    import yaml
    
    config_file = tmp_path / "config.yaml"
    with open(config_file, "w") as f:
        yaml.dump(sample_config, f)
    return config_file


# ============================================================================
# Model Fixtures
# ============================================================================

@pytest.fixture
def mock_model():
    """Create a mock model object."""
    model = Mock()
    model.name = "test-model"
    model.utilization = 50
    model.available = True
    model.last_request_time = None
    return model


@pytest.fixture
def model_list(mock_model) -> List[Mock]:
    """Create a list of mock models."""
    models = []
    for i, name in enumerate(["model-a", "model-b", "model-c"]):
        model = Mock()
        model.name = name
        model.utilization = (i + 1) * 20
        model.available = True
        model.last_request_time = None
        models.append(model)
    return models


# ============================================================================
# HTTP Client Fixtures
# ============================================================================

@pytest.fixture
def mock_http_response():
    """Create a mock HTTP response."""
    response = Mock()
    response.status_code = 200
    response.headers = {"Content-Type": "application/json"}
    response.json.return_value = {"choices": [{"message": {"content": "test"}}]}
    response.text = '{"choices": [{"message": {"content": "test"}}]}'
    response.raise_for_status = Mock()
    return response


@pytest.fixture
def mock_http_client(mocker):
    """Create a mock HTTP client."""
    client = Mock()
    client.get = Mock()
    client.post = Mock()
    client.put = Mock()
    client.delete = Mock()
    client.close = Mock()
    return client


# ============================================================================
# Cache Fixtures
# ============================================================================

@pytest.fixture
def cache_config():
    """Cache configuration for testing."""
    return {
        "ttl": 60,
        "max_size": 100,
        "eviction_policy": "lru",
    }


# ============================================================================
# Server Fixtures
# ============================================================================

@pytest.fixture
def app_client():
    """Create test client for the proxy app."""
    from litellm_proxy.server.app import create_app
    from litellm_proxy.config.loader import ProxyConfig
    
    config = ProxyConfig(
        models=[{"name": "test-model", "api_base": "https://test.api"}],
        routing_strategy="chutes_utilization",
        cache_ttl=30,
    )
    app = create_app(config)
    with TestClient(app) as client:
        yield client


@pytest.fixture
def running_server():
    """Start proxy server in subprocess for integration tests."""
    import subprocess
    import time
    import requests
    
    proc = subprocess.Popen(
        ["python", "-m", "litellm_proxy", "server", "--port", "8765"],
        env={**os.environ, "LITELLM_MODELS": "test-model"},
    )
    time.sleep(3)  # Wait for startup
    
    yield "http://localhost:8765"
    
    proc.terminate()
    proc.wait(timeout=5)


# ============================================================================
# Helper Fixtures
# ============================================================================

@pytest.fixture
def reset_singletons():
    """Reset any singleton state between tests."""
    yield
    # Cleanup code here


@pytest.fixture(autouse=True)
def reset_module_state():
    """Reset module-level state before each test."""
    # This runs before each test
    yield
    # Cleanup after each test
```

## Mocking Strategy

### 1. HTTP Request Mocking

Use `requests-mock` or `responses` library for HTTP mocking:

```python
import responses
import pytest

@responses.activate
def test_api_client_get_request():
    """Test API client with mocked HTTP responses."""
    responses.add(
        responses.GET,
        "http://localhost:8000/health",
        json={"status": "healthy"},
        status=200
    )
    
    # Make actual HTTP call
    result = make_http_request("http://localhost:8000/health")
    
    assert result["status"] == "healthy"
```

### 2. File System Mocking

Use `pyfakefs` or `tempfile` for file operations:

```python
def test_config_missing_yaml_file(tmp_path):
    """Test config loading when YAML file is missing."""
    with pytest.raises(FileNotFoundError):
        load_config(config_file=str(tmp_path / "missing.yaml"))
```

### 3. Environment Variable Mocking

Use pytest's `monkeypatch`:

```python
def test_config_env_override(monkeypatch):
    """Test environment variable override."""
    monkeypatch.setenv("LB_PORT", "9000")
    config = load_config()
    assert config.port == 9000
```

### 4. Time-Based Mocking

Use `freezegun` for time-based tests:

```python
from freezegun import freeze_time

@freeze_time("2024-01-01 00:00:00")
def test_cache_expiration():
    """Test cache expiration."""
    cache.set("key", "value", ttl=60)
    
    # Advance time
    freeze_time("2024-01-01 00:01:01")
    
    assert cache.get("key") is None
```

### 5. Async Mocking

Use `pytest-asyncio`:

```python
import pytest
import asyncio

@pytest.mark.asyncio
async def test_async_routing():
    """Test async routing function."""
    result = await select_model_async(models)
    assert result is not None
```

## Test Execution Order

### Default Execution Order

By default, pytest runs tests in the following order:

1. **Unit Tests** - Run first (fastest, most isolated)
2. **Integration Tests** - Run second (component interaction)
3. **E2E Tests** - Run last (slowest, full workflow)

### Parallel Execution

Use `pytest-xdist` for parallel test execution:

```bash
# Run tests in parallel
pytest -n auto

# Run with 4 workers
pytest -n 4
```

### Execution Groups

Define test execution groups using markers:

```python
# Run only unit tests
pytest -m unit

# Run unit and integration, skip E2E
pytest -m "unit or integration"

# Skip slow tests
pytest -m "not slow"
```

### CI/CD Pipeline

```yaml
# Example GitHub Actions workflow
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install pytest pytest-cov pytest-xdist
          pip install -e .
      
      - name: Run unit tests
        run: pytest -m unit -v
      
      - name: Run integration tests
        run: pytest -m integration -v
      
      - name: Run E2E tests
        run: pytest -m e2e -v
      
      - name: Generate coverage report
        run: pytest --cov --cov-report=xml
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

## Test Function Naming Convention

### Naming Pattern

```
test_<module>_<functionality>_<expected_behavior>
```

### Examples

```python
# Unit test examples
def test_routing_selects_lowest_utilization():
    """Test routing selects model with lowest utilization."""
    pass

def test_config_cli_overrides_env():
    """Test CLI arguments override environment variables."""
    pass

def test_cache_ttl_expiration():
    """Test cache entries expire after TTL."""
    pass

# Integration test examples
def test_health_endpoint_returns_200():
    """Test health endpoint returns success status."""
    pass

def test_config_hot_reload():
    """Test configuration reloads on file change."""
    pass

# E2E test examples
def test_e2e_basic_chat_flow():
    """Test complete chat completion flow."""
    pass

def test_e2e_load_balancing():
    """Test load balancing across models."""
    pass
```

## Given-When-Then Format

Each test should follow the Given-When-Then format in docstrings:

```python
def test_routing_selects_lowest_utilization():
    """
    Test that routing selects the model with lowest utilization.
    
    Given: A list of models with different utilization percentages
           models = [
               Model(name='model-a', utilization=80),
               Model(name='model-b', utilization=20),
               Model(name='model-c', utilization=50),
           ]
    When:  Calling select_model(models)
    Then:  Returns model-b (lowest utilization = 20%)
    """
    # Implementation
```

## Error Assertion Patterns

### Using pytest.raises

```python
def test_config_missing_required_field():
    """Test that missing required field raises error."""
    with pytest.raises(ConfigurationError) as exc_info:
        load_config({})
    
    assert "required" in str(exc_info.value).lower()
```

### Using pytest.warns

```python
def test_config_deprecated_option():
    """Test that deprecated options emit warnings."""
    with pytest.warns(DeprecationWarning):
        load_config({"deprecated_option": "value"})
```

### Using pytest.fail

```python
def test_unexpected_behavior():
    """Test unexpected behavior."""
    if unexpected_condition:
        pytest.fail("Unexpected condition occurred")
```

## Fixtures for Common Patterns

### Retry Testing

```python
@pytest.fixture
def flaky_service(mocker):
    """Create a service that fails then succeeds."""
    call_count = 0
    
    def flaky_call(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ConnectionError("Service unavailable")
        return {"success": True}
    
    return flaky_call
```

### Rate Limiting

```python
@pytest.fixture
def rate_limited_service():
    """Create a rate-limited service mock."""
    class RateLimitedService:
        def __init__(self):
            self.call_count = 0
            self.reset_time = None
        
        def call(self):
            self.call_count += 1
            if self.call_count > 10:
                raise RateLimitError("Rate limit exceeded")
            return {"success": True}
    
    return RateLimitedService()
```

## Coverage Measurement

### Measuring Coverage

```bash
# Run with coverage
pytest --cov=. --cov-report=term-missing

# Generate HTML report
pytest --cov=. --cov-report=html

# Minimum coverage enforcement
pytest --cov=. --cov-fail-under=80
```

### Coverage Reports

| Report Type | Command | Output |
|-------------|---------|--------|
| Terminal | `--cov-report=term-missing` | Colored terminal output |
| HTML | `--cov-report=html` | `htmlcov/index.html` |
| XML | `--cov-report=xml` | `coverage.xml` |
| JSON | `--cov-report=json` | `coverage.json` |

## Test Isolation

### Ensuring Test Isolation

1. **Each test is independent** - No test depends on another
2. **Fixtures provide fresh state** - Use `function` scope for mutable fixtures
3. **Cleanup in fixtures** - Use `yield` for teardown
4. **No shared global state** - Avoid module-level globals

### Example: Proper Isolation

```python
@pytest.fixture
def fresh_cache():
    """Create a fresh cache for each test."""
    cache = Cache(ttl=60, max_size=100)
    yield cache
    # Cleanup: cache is automatically garbage collected
```

## Performance Testing

### Slow Test Detection

```bash
# Show slowest 10 tests
pytest --durations=10

# Mark tests as slow
@pytest.mark.slow
def test_very_slow_operation():
    """This test takes a long time."""
    pass

# Skip slow tests in CI
pytest -m "not slow"
```

### Memory Leak Detection

```bash
# Use pytest-memprof (if available)
pytest --memprof
```

## Integration with Development Workflow

### Pre-commit Hook

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/pytest-dev/pytest
    rev: 7.4.0
    hooks:
      - id: pytest
        args: [--strict-markers, -m, "not e2e"]
```

### IDE Integration

#### VS Code (settings.json)

```json
{
  "python.testing.pytestEnabled": true,
  "python.testing.pytestArgs": [
    "tests",
    "-v",
    "--cov=.",
    "--cov-report=term-missing"
  ]
}
```

#### PyCharm

1. Run > Edit Configurations
2. Add pytest configuration
3. Set test folder to `tests`
4. Add coverage if desired

## Summary

This design provides a comprehensive framework for implementing VDD test criteria:

1. **Clear directory structure** for organizing tests by type
2. **Shared fixtures** for common test data and mock objects
3. **Mocking strategies** for external dependencies
4. **Execution patterns** for different test categories
5. **CI/CD integration** for automated testing
6. **Coverage measurement** for quality metrics

All test implementations should follow these patterns to ensure consistency and maintainability.
