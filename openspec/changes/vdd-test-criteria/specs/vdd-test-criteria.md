# ADDED: VDD Test Criteria for chutes-load-balancer

## Summary

This document defines comprehensive Verification-Driven Development (VDD) test criteria for the chutes-load-balancer system. It establishes test cases, acceptance criteria, verification scripts, success metrics, and edge case scenarios that agents can use to self-verify their implementations.

## Specification

### 1. Test Case Specifications

#### 1.1 Unit Tests - Routing Logic (7 tests)

##### Test: test_routing_selects_lowest_utilization_model

**Given**: A list of models with different utilization percentages
**When**: Calling the routing selection function
**Then**: Should return the model with the lowest utilization

```python
def test_routing_selects_lowest_utilization_model():
    """
    Test that routing selects model with lowest utilization.
    
    Given: models = [{'name': 'model-a', 'utilization': 80}, 
                     {'name': 'model-b', 'utilization': 20},
                     {'name': 'model-c', 'utilization': 50}]
    When: select_model(models)
    Then: Returns 'model-b' (lowest utilization)
    """
    pass
```

##### Test: test_routing_equal_utilization_round_robin

**Given**: Multiple models with equal utilization
**When**: Calling the routing selection function
**Then**: Should distribute requests using round-robin

##### Test: test_routing_empty_model_list

**Given**: An empty list of models
**When**: Calling the routing selection function
**Then**: Should raise EmptyModelListError or return None

##### Test: test_routing_single_model

**Given**: A list with only one model
**When**: Calling the routing selection function
**Then**: Should always return that model regardless of utilization

##### Test: test_routing_model_factory

**Given**: Model configuration data
**When**: Creating model instances via factory
**Then**: Should create properly initialized model objects

##### Test: test_routing_updates_utilization

**Given**: A model is selected for a request
**When**: After request completion callback
**Then**: Should increment utilization counter

##### Test: test_routing_filters_unavailable_models

**Given**: A mix of available and unavailable models
**When**: Calling the routing selection function
**Then**: Should exclude unavailable models from selection

#### 1.2 Unit Tests - Configuration Loading (10 tests)

##### Test: test_config_cli_args_override_env

**Given**: CLI arguments and environment variables both set
**When**: Loading configuration
**Then**: CLI arguments take precedence

##### Test: test_config_env_vars_override_yaml

**Given**: Environment variables and YAML file both set
**When**: Loading configuration
**Then**: Environment variables take precedence

##### Test: test_config_yaml_defaults

**Given**: No CLI args or environment variables
**When**: Loading configuration
**Then**: Should use YAML file defaults

##### Test: test_config_missing_yaml_file

**Given**: YAML config file does not exist
**When**: Loading configuration
**Then**: Should raise FileNotFoundError or use defaults

##### Test: test_config_invalid_yaml_format

**Given**: YAML file with invalid syntax
**When**: Loading configuration
**Then**: Should raise yaml.YAMLError

##### Test: test_config_parse_model_list

**Given**: Valid model configuration in YAML
**When**: Parsing model list
**Then**: Should return list of ModelConfig objects

##### Test: test_config_parse_routing_params

**Given**: Valid routing parameters in config
**When**: Parsing routing configuration
**Then**: Should return RoutingConfig with correct values

##### Test: test_config_env_var_prefix

**Given**: Environment variables with correct prefix (LB_)
**When**: Loading configuration
**Then**: Should map to corresponding config keys

##### Test: test_config_missing_required_field

**Given**: Configuration missing required field
**When**: Validating configuration
**Then**: Should raise ConfigurationError

##### Test: test_config_type_coercion

**Given**: String values that should be integers
**When**: Parsing configuration
**Then**: Should coerce to correct types

#### 1.3 Unit Tests - Cache Behavior (8 tests)

##### Test: test_cache_ttl_expiration

**Given**: Cache entry with TTL of 60 seconds
**When**: 61 seconds have passed
**Then**: Entry should be considered expired

##### Test: test_cache_get_returns_cached

**Given**: Valid cached entry exists
**When**: Getting value from cache
**Then**: Should return cached value

##### Test: test_cache_get_returns_none_for_expired

**Given**: Expired cache entry
**When**: Getting value from cache
**Then**: Should return None

##### Test: test_cache_set_updates_existing

**Given**: Existing cache entry
**When**: Setting new value for same key
**Then**: Should update the entry

##### Test: test_cache_thread_safety

```
Given: Cache with concurrent read/write operations
When: 1000 operations across 10 threads simultaneously
Then: 
    - No exceptions raised
    - Final item count matches expected
    - All values correctly stored/retrieved
```

```python
def test_cache_thread_safety():
    """
    Given: Cache with concurrent read/write operations
    When: 1000 operations across 10 threads simultaneously
    Then: 
        - No exceptions raised
        - Final item count matches expected
        - All values correctly stored/retrieved
    """
    # Implementation approach:
    # 1. Create cache instance
    # 2. Spawn 10 threads, each doing 100 set/get operations
    # 3. Use threading.Barrier to synchronize start
    # 4. Verify no exceptions and data integrity
    pass
```

##### Test: test_cache_max_size_eviction

**Given**: Cache at maximum size
**When**: Adding new entry
**Then**: Should evict oldest entry (LRU)

##### Test: test_cache_clear

**Given**: Cache with multiple entries
**When**: Calling clear()
**Then**: All entries should be removed

##### Test: test_cache_delete

**Given**: Cache with specific entry
**When**: Deleting entry by key
**Then**: Entry should be removed

#### 1.4 Unit Tests - API Client (7 tests)

##### Test: test_api_client_get_request

**Given**: Valid GET endpoint
**When**: Making GET request
**Then**: Should return parsed JSON response

##### Test: test_api_client_post_request

**Given**: Valid POST endpoint with data
**When**: Making POST request
**Then**: Should return parsed JSON response

##### Test: test_api_client_retry_on_5xx

**Given**: Server returns 503 initially
**When**: Making request with retry enabled
**Then**: Should retry up to max_retries and succeed or fail

##### Test: test_api_client_no_retry_on_4xx

**Given**: Server returns 400
**When**: Making request
**Then**: Should not retry, raise immediately

##### Test: test_api_client_timeout

**Given**: Slow server
**When**: Request exceeds timeout
**Then**: Should raise TimeoutError

##### Test: test_api_client_connection_error

**Given**: Server is unreachable
**When**: Making request
**Then**: Should raise ConnectionError

##### Test: test_api_client_rate_limit_handling

**Given**: Server returns 429
**When**: Making request
**Then**: Should respect Retry-After header if present

#### 1.5 Integration Tests - Endpoints (8 tests)

##### Test: test_health_endpoint_returns_200

**Given**: Server is running
**When**: GET /health
**Then**: Returns 200 with status: healthy

##### Test: test_health_endpoint_includes_models

**Given**: Server is running with models loaded
**When**: GET /health
**Then**: Response includes model list and utilization

##### Test: test_chat_completions_basic

**Given**: Valid chat completion request
**When**: POST /v1/chat/completions
**Then**: Returns valid completion response

##### Test: test_chat_completions_streaming

**Given**: Streaming chat completion request
**When**: POST /v1/chat/completions with stream: true
**Then**: Returns SSE stream

##### Test: test_chat_completions_invalid_model

**Given**: Request with non-existent model
**When**: POST /v1/chat/completions
**Then**: Returns 400 error

##### Test: test_chat_completions_rate_limit

**Given**: Too many requests
**When**: POST /v1/chat/completions
**Then**: Returns 429 with retry information

##### Test: test_metrics_endpoint

**Given**: Server is running
**When**: GET /metrics
**Then**: Returns Prometheus-formatted metrics

##### Test: test_model_list_endpoint

**Given**: Server is running
**When**: GET /v1/models
**Then**: Returns list of available models

#### 1.6 Integration Tests - Config Loading (5 tests)

##### Test: test_config_hot_reload

**Given**: Server running with config
**When**: Config file is modified
**Then**: Should reload configuration

##### Test: test_config_invalid_reload

**Given**: Server running
**When**: Config file is replaced with invalid content
**Then**: Should keep old config, log error

##### Test: test_config_env_change_detected

**Given**: Server running with ENV config
**When**: Environment variable changes
**Then**: Should detect and reload

##### Test: test_config_multiple_sources

**Given**: CLI args, ENV vars, and YAML all present
**When**: Loading configuration
**Then**: Precedence correctly applied

##### Test: test_config_partial_override

**Given**: Only some values overridden via CLI
**When**: Loading configuration
**Then**: Non-overridden values come from YAML

#### 1.7 Integration Tests - Model Switching (3 tests)

##### Test: test_model_failover_primary_to_secondary

**Given**: Primary model unavailable
**When**: Request comes in
**Then**: Should route to secondary model

##### Test: test_model_failover_exhaustion

**Given**: All models unavailable
**When**: Request comes in
**Then**: Should return error with available models list

##### Test: test_model_recovery

**Given**: Failed model becomes available again
**When**: Utilization check runs
**Then**: Should include model back in selection

#### 1.8 E2E Tests (6 tests)

##### Test: test_e2e_basic_chat_flow

**Given**: Server running with default config
**When**: User sends chat completion request
**Then**: Receives valid response from model

##### Test: test_e2e_load_balancing

**Given**: Multiple concurrent requests
**When**: Requests distributed across models
**Then**: Utilization is balanced

##### Test: test_e2e_config_via_env

**Given**: Configuration via environment variables
**When**: Server starts
**Then**: Uses environment configuration

##### Test: test_e2e_config_via_cli

**Given**: Configuration via CLI arguments
**When**: Server starts
**Then**: Uses CLI configuration

##### Test: test_e2e_graceful_shutdown

**Given**: Server handling requests
**When**: SIGTERM received
**Then**: Completes in-flight requests, stops accepting new

##### Test: test_e2e_logging_output

**Given**: Server running
**When**: Requests are made
**Then**: Logs appear in correct format and level

#### 1.9 LiteLLM Proxy Integration Tests

**Test Module:** `tests/integration/test_litellm_proxy.py`

##### Test: test_litellm_proxy_startup

```
Given: Valid LiteLLM config with models
When: Proxy server starts
Then: Server binds to port and responds to /health
```

##### Test: test_litellm_config_loading

```
Given: litellm-config.yaml with model definitions
When: Proxy loads config
Then: All models are registered in router
```

##### Test: test_litellm_request_routing

```
Given: Proxy with multiple models configured
When: POST /v1/chat/completions request
Then: Request routed to correct upstream model
```

##### Test: test_litellm_error_handling

```
Given: Upstream model returns error
When: Request is made
Then: Error is propagated with appropriate status code
```

##### Test: test_litellm_streaming_response

```
Given: Streaming request to /v1/chat/completions
When: Request is made with stream=true
Then: Server-sent events are properly forwarded
```

#### 1.10 Security Tests

**Test Module:** `tests/integration/test_security.py`

##### Test: test_api_key_required

```
Given: Request without API key
When: POST /v1/chat/completions
Then: Returns 401 Unauthorized
```

##### Test: test_invalid_api_key_rejected

```
Given: Request with invalid API key
When: POST /v1/chat/completions
Then: Returns 403 Forbidden
```

##### Test: test_input_sanitization

```
Given: Request with malicious input (SQL injection, XSS)
When: POST /v1/chat/completions
Then: Input is sanitized, no injection occurs
```

##### Test: test_rate_limit_enforcement

```
Given: Multiple rapid requests exceeding rate limit
When: Requests are made
Then: Returns 429 Too Many Requests after limit
```

##### Test: test_error_messages_no_leak

```
Given: Request that triggers error
When: Error response returned
Then: Error message doesn't leak internal details
```

---

### 2. Acceptance Criteria (18 total)

#### CLI Interface (AC-1 to AC-6)

| ID | Criterion | Test Function |
|----|-----------|---------------|
| AC-1 | CLI accepts --host argument | test_cli_host_argument |
| AC-2 | CLI accepts --port argument | test_cli_port_argument |
| AC-3 | CLI accepts --config argument | test_cli_config_argument |
| AC-4 | CLI --help shows all options | test_cli_help_output |
| AC-5 | CLI validates port range (1-65535) | test_cli_port_validation |
| AC-6 | CLI exits with code 0 on --version | test_cli_version_output |

#### Configuration Loading (AC-7 to AC-11)

| ID | Criterion | Test Function |
|----|-----------|---------------|
| AC-7 | CLI args override environment variables | test_config_cli_overrides_env |
| AC-8 | Environment variables override YAML | test_config_env_overrides_yaml |
| AC-9 | YAML provides default values | test_config_yaml_defaults |
| AC-10 | Missing required fields raise error | test_config_missing_required |
| AC-11 | Invalid config file format raises error | test_config_invalid_format |

#### Routing Behavior (AC-12 to AC-14)

| ID | Criterion | Test Function |
|----|-----------|---------------|
| AC-12 | Routes to lowest utilization model | test_routing_selects_lowest |
| AC-13 | Round-robin on equal utilization | test_routing_round_robin |
| AC-14 | Fails over on model unavailability | test_routing_failover |

#### Server Endpoints (AC-15 to AC-18)

| ID | Criterion | Test Function |
|----|-----------|---------------|
| AC-15 | /health returns 200 when healthy | test_health_endpoint |
| AC-16 | /v1/chat/completions processes requests | test_chat_endpoint |
| AC-17 | /v1/models returns model list | test_models_endpoint |
| AC-18 | Invalid requests return appropriate errors | test_error_responses |

---

### 3. Verification Scripts

#### 3.1 verify_package_structure.py

```python
#!/usr/bin/env python3
"""
Verify test package structure is correct.

Checks:
- tests/ directory exists
- tests/unit/ directory exists
- tests/integration/ directory exists
- tests/e2e/ directory exists
- conftest.py exists in tests/
- pyproject.toml has pytest configuration
"""

import os
import sys
from pathlib import Path

def verify_package_structure():
    """Verify the test package structure is correct."""
    root = Path(__file__).parent.parent
    
    required_dirs = [
        "tests",
        "tests/unit",
        "tests/integration", 
        "tests/e2e",
    ]
    
    required_files = [
        "tests/conftest.py",
        "pyproject.toml",
    ]
    
    errors = []
    
    for dir_path in required_dirs:
        full_path = root / dir_path
        if not full_path.exists():
            errors.append(f"Missing directory: {dir_path}")
        elif not full_path.is_dir():
            errors.append(f"Path is not a directory: {dir_path}")
    
    for file_path in required_files:
        full_path = root / file_path
        if not full_path.exists():
            errors.append(f"Missing file: {file_path}")
        elif not full_path.is_file():
            errors.append(f"Path is not a file: {file_path}")
    
    if errors:
        print("FAILED: Package structure verification failed")
        for error in errors:
            print(f"  - {error}")
        return False
    
    print("PASSED: Package structure verified")
    return True

if __name__ == "__main__":
    success = verify_package_structure()
    sys.exit(0 if success else 1)
```

#### 3.2 verify_no_hardcoded_models.py

```python
#!/usr/bin/env python3
"""
Verify no hardcoded model names in source code.

Checks:
- No hardcoded model names like 'moonshotai', 'zai-org', 'Qwen'
- Model names should come from configuration
"""

import os
import re
import sys
from pathlib import Path

# Files to EXCLUDE from the check (these legitimately contain model names)
EXCLUDED_PATTERNS = [
    "*.yaml",
    "*.yml", 
    "*.json",
    "*.md",
    "*.rst",
    "*.txt",
]

# Only check Python source files
SOURCE_EXTENSIONS = [".py"]

HARDCODED_MODELS = [
    r'\bmoonshotai\b',
    r'\bzai-org\b', 
    r'\bQwen\b',
    r'\bkimi\b',
    r'\bglm\b',
]

def matches_excluded_pattern(file_path: Path) -> bool:
    """Check if file matches excluded patterns."""
    for pattern in EXCLUDED_PATTERNS:
        if pattern.startswith("*."):
            ext = pattern[1:]
            if file_path.suffix == ext:
                return True
        elif pattern in str(file_path):
            return True
    return False

def check_file(file_path: Path, patterns: list) -> list:
    """Check a single file for hardcoded models."""
    violations = []
    
    # Skip excluded patterns
    if matches_excluded_pattern(file_path):
        return violations
    
    try:
        content = file_path.read_text()
    except (UnicodeDecodeError, IOError):
        return violations
    
    for pattern in patterns:
        matches = re.finditer(pattern, content, re.IGNORECASE)
        for match in matches:
            line_num = content[:match.start()].count('\n') + 1
            violations.append(
                f"{file_path}:{line_num}: Found hardcoded model: {match.group()}"
            )
    
    return violations

def verify_no_hardcoded_models():
    """Verify no hardcoded model names in source."""
    root = Path(__file__).parent.parent
    
    # Get all Python source files
    source_files = []
    for ext in SOURCE_EXTENSIONS:
        source_files.extend(root.glob(f"**/*{ext}"))
    
    # Filter out test files, virtual environments, and cache
    source_files = [
        f for f in source_files 
        if 'test' not in str(f).lower()
        and '.venv' not in str(f) 
        and '__pycache__' not in str(f)
        and 'venv' not in str(f)
        and '.git' not in str(f)
    ]
    
    violations = []
    
    for source_file in source_files:
        file_violations = check_file(source_file, HARDCODED_MODELS)
        violations.extend(file_violations)
    
    if violations:
        print("FAILED: Hardcoded models found")
        for violation in violations:
            print(f"  - {violation}")
        return False
    
    print("PASSED: No hardcoded models found")
    return True

if __name__ == "__main__":
    success = verify_no_hardcoded_models()
    sys.exit(0 if success else 1)
```

#### 3.3 verify_shell_scripts_deprecated.py

```python
#!/usr/bin/env python3
"""
Verify shell scripts are deprecated in favor of Python tests.

Checks:
- No shell scripts in tests/ directory
- No shell scripts in scripts/ that are used for testing
- Python tests provide equivalent coverage
"""

import os
import sys
from pathlib import Path

def verify_shell_scripts_deprecated():
    """Verify shell scripts are deprecated."""
    root = Path(__file__).parent.parent
    
    # Check for shell scripts in tests directory
    tests_dir = root / "tests"
    if tests_dir.exists():
        shell_scripts = list(tests_dir.glob("*.sh"))
        if shell_scripts:
            print(f"FAILED: Found shell scripts in tests/: {shell_scripts}")
            return False
    
    # Check scripts directory for test-related scripts
    scripts_dir = root / "scripts"
    test_scripts = []
    if scripts_dir.exists():
        for script in scripts_dir.glob("*"):
            if script.suffix in ['.sh', '.bash'] and 'test' in script.name.lower():
                test_scripts.append(script)
    
    if test_scripts:
        print(f"WARNING: Found test-related shell scripts: {test_scripts}")
        print("  These should be converted to Python tests")
        return False
    
    print("PASSED: Shell scripts deprecated")
    return True

if __name__ == "__main__":
    success = verify_shell_scripts_deprecated()
    sys.exit(0 if success else 1)
```

#### 3.4 verify_python_equivalence.py

```python
#!/usr/bin/env python3
"""
Verify Python tests provide equivalent coverage to original shell scripts.

Checks:
- Minimum number of test files (>= 10)
- Minimum number of test functions (>= 30)
- All major modules have tests
"""

import os
import sys
import subprocess
from pathlib import Path

def verify_cli_features(root_dir: Path) -> tuple[bool, list[str]]:
    """Verify CLI has required features."""
    errors = []
    
    try:
        result = subprocess.run(
            ["pytest", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            errors.append("pytest not installed - run: pip install pytest")
            return False, errors
    except FileNotFoundError:
        errors.append("pytest not installed - run: pip install pytest")
        return False, errors
    
    # ... rest of the function

def verify_python_equivalence():
    """Verify Python tests provide equivalent coverage."""
    root = Path(__file__).parent.parent
    
    # Count test files
    tests_dir = root / "tests"
    if not tests_dir.exists():
        print("FAILED: tests/ directory not found")
        return False
    
    test_files = list(tests_dir.glob("**/test_*.py"))
    test_files += list(tests_dir.glob("**/*_test.py"))
    
    print(f"Found {len(test_files)} test files")
    
    if len(test_files) < 10:
        print(f"FAILED: Expected at least 10 test files, found {len(test_files)}")
        return False
    
    # Count test functions using pytest
    try:
        result = subprocess.run(
            ["python", "-m", "pytest", "--collect-only", "-q"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        # Parse output for test count
        output = result.stdout + result.stderr
        import re
        match = re.search(r'(\d+) test', output)
        if match:
            test_count = int(match.group(1))
            print(f"Found {test_count} test functions")
            
            if test_count < 30:
                print(f"FAILED: Expected at least 30 tests, found {test_count}")
                return False
        else:
            print("WARNING: Could not determine test count")
    except FileNotFoundError:
        print("WARNING: pytest not installed - cannot verify test count")
    except subprocess.TimeoutExpired:
        print("WARNING: pytest timed out - cannot verify test count")
    except Exception as e:
        print(f"WARNING: Could not run pytest: {e}")
    
    print("PASSED: Python tests provide equivalent coverage")
    return True

if __name__ == "__main__":
    success = verify_python_equivalence()
    sys.exit(0 if success else 1)
```

---

### 4. Success Metrics

| Metric | Target | Measurement Method |
|--------|--------|-------------------|
| Code Coverage | >= 70% (80% after Phase 0 refactoring) | pytest --cov |
| Unit Tests | >= 30 | pytest --collect-only |
| Integration Tests | >= 10 | pytest --collect-only |
| E2E Tests | >= 5 | pytest --collect-only |
| Total Test Functions | >= 54 | pytest --collect-only |
| Acceptance Criteria | 18/18 | All ACs passing |
| Verification Scripts | 4/4 | All scripts passing |
| Hardcoded Models | 0 | verify_no_hardcoded_models.py |
| Shell Test Scripts | 0 | verify_shell_scripts_deprecated.py |
| Test Execution Time | < 60s | pytest --durations=10 |
| Flaky Tests | 0 | pytest --reruns |

---

### 5. Edge Cases

#### 5.1 Configuration Edge Cases

| ID | Scenario | Expected Behavior |
|----|----------|-------------------|
| EC-1 | Empty YAML file | Use all defaults |
| EC-2 | YAML with only comments | Treat as empty, use defaults |
| EC-3 | Duplicate keys in YAML | Last value wins |
| EC-4 | Extra fields in YAML | Ignore extra fields |
| EC-5 | Environment variable with empty value | Treat as not set |
| EC-6 | CLI argument with empty value | Treat as not set |
| EC-7 | Config file path with tilde expansion | Expand to home directory |
| EC-8 | Config file path with environment variables | Expand before reading |
| EC-9 | Very long config value | Truncate or error |
| EC-10 | Unicode in config values | Handle correctly |

#### 5.2 Routing Edge Cases

| ID | Scenario | Expected Behavior |
|----|----------|-------------------|
| EC-11 | All models at 100% utilization | Return any model (best effort) |
| EC-12 | Model with negative utilization | Treat as 0% |
| EC-13 | Model with utilization > 100% | Cap at 100% |
| EC-14 | Model utilization not a number | Skip model, log warning |
| EC-15 | Model added while requests in flight | Include in next selection |
| EC-16 | Model removed while requests in flight | Complete in-flight, exclude from selection |
| EC-17 | Rapid model additions/removals | Debounce updates |
| EC-18 | Model with very long name | Truncate display, handle correctly |

#### 5.3 Network/API Edge Cases

| ID | Scenario | Expected Behavior |
|----|----------|-------------------|
| EC-19 | Server responds with 502 | Retry with backoff |
| EC-20 | Server responds with 503 | Retry with backoff |
| EC-21 | Server responds with 504 | Retry with backoff |
| EC-22 | Response body is not JSON | Raise appropriate error |
| EC-23 | Response body is empty | Raise appropriate error |
| EC-24 | Request times out on connect | Raise ConnectionError |
| EC-25 | SSL certificate error | Raise SSLError |
| EC-26 | Too many redirects | Raise TooManyRedirects |
| EC-27 | Request canceled by user | Raise CanceledError |
| EC-28 | Response body too large | Raise ContentTooLargeError |

#### 5.4 Server Edge Cases

| ID | Scenario | Expected Behavior |
|----|----------|-------------------|
| EC-29 | SIGTERM during request | Complete request, then shutdown |
| EC-30 | SIGINT during request | Complete request, then shutdown |
| EC-31 | Memory limit exceeded | Return 503, log error |
| EC-32 | Disk full (for logs) | Continue logging to stdout |
| EC-33 | Too many open files | Return 503, log error |
| EC-34 | Thread pool exhausted | Queue requests, return 503 when full |
| EC-35 | Child process dies | Restart or fail gracefully |
| EC-36 | Port already in use | Exit with clear error message |
| EC-37 | Binding to localhost vs 0.0.0.0 | Respect --host argument |
| EC-38 | Invalid HTTP method | Return 405 Method Not Allowed |

---

## Files Changed

The following files will be created:

### New Test Files

- `tests/__init__.py` - Package marker
- `tests/unit/__init__.py` - Package marker
- `tests/unit/test_routing.py` - Routing logic tests (7 tests)
- `tests/unit/test_config.py` - Config loading tests (10 tests)
- `tests/unit/test_cache.py` - Cache behavior tests (8 tests)
- `tests/unit/test_api_client.py` - API client tests (7 tests)
- `tests/integration/__init__.py` - Package marker
- `tests/integration/test_endpoints.py` - Endpoint tests (8 tests)
- `tests/integration/test_config_loading.py` - Config loading integration (5 tests)
- `tests/integration/test_model_switching.py` - Model switching tests (3 tests)
- `tests/e2e/__init__.py` - Package marker
- `tests/e2e/test_full_flows.py` - E2E tests (6 tests)
- `tests/conftest.py` - Pytest fixtures and configuration

### New Configuration Files

- `pyproject.toml` - Project configuration with pytest settings

### New Verification Scripts

- `scripts/verify_package_structure.py` - Verify test structure
- `scripts/verify_no_hardcoded_models.py` - Check for hardcoded models
- `scripts/verify_shell_scripts_deprecated.py` - Verify shell deprecation
- `scripts/verify_python_equivalence.py` - Verify Python test coverage

## Verification

To verify this change is correctly implemented:

1. **Run all tests**: `pytest tests/ -v`
2. **Check coverage**: `pytest tests/ --cov --cov-report=term-missing`
3. **Run verification scripts**:
   - `python scripts/verify_package_structure.py`
   - `python scripts/verify_no_hardcoded_models.py`
   - `python scripts/verify_shell_scripts_deprecated.py`
   - `python scripts/verify_python_equivalence.py`
4. **Verify acceptance criteria**: All 18 ACs must pass

Expected results:
- All 54+ tests pass
- Code coverage >= 70% (80% after Phase 0 refactoring)
- All 4 verification scripts pass
- No hardcoded models found
- No shell test scripts remaining
