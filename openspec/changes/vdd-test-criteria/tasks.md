# TASKS: VDD Test Criteria Implementation

## Overview

This document contains the implementation checklist for the VDD test criteria change. Each task represents a discrete unit of work that can be independently verified.

---

## Phase 0: Code Refactoring (Prerequisite)

Before implementing tests, refactor the monolithic code into testable modules:

- [ ] **P0.1** Create `src/litellm_proxy/` package structure
- [ ] **P0.2** Extract routing logic from `chutes_routing.py` into `src/litellm_proxy/routing/strategy.py`
- [ ] **P0.3** Extract cache logic into `src/litellm_proxy/cache/store.py`
- [ ] **P0.4** Extract API client into `src/litellm_proxy/api/client.py`
- [ ] **P0.5** Define custom exceptions in `src/litellm_proxy/exceptions.py`
- [ ] **P0.6** Create `src/litellm_proxy/config/loader.py` for config loading
- [ ] **P0.7** Update imports in existing files to use new modules
- [ ] **P0.8** Verify refactored code works with existing proxy

### Custom Exceptions (src/litellm_proxy/exceptions.py)

```python
class ChutesRoutingError(Exception):
    """Base exception for routing errors."""
    pass

class EmptyModelListError(ChutesRoutingError):
    """Raised when no models are configured."""
    pass

class ConfigurationError(ChutesRoutingError):
    """Raised when configuration is invalid."""
    pass

class ModelUnavailableError(ChutesRoutingError):
    """Raised when a model is unavailable."""
    pass

class RateLimitError(ChutesRoutingError):
    """Raised when rate limit is exceeded."""
    pass

class ChutesAPIError(Exception):
    """Base exception for Chutes API errors."""
    pass

class ChutesAPIConnectionError(ChutesAPIError):
    """Raised when connection to Chutes API fails."""
    pass
```

**Verification**: Verify all imports work and existing functionality is preserved

---

## Phase 1: Infrastructure Setup

### Task 1: Create Test Directory Structure

- [ ] **T1.1** Create `tests/` directory root
- [ ] **T1.2** Create `tests/unit/` subdirectory
- [ ] **T1.3** Create `tests/integration/` subdirectory
- [ ] **T1.4** Create `tests/e2e/` subdirectory
- [ ] **T1.5** Create `tests/__init__.py` package marker
- [ ] **T1.6** Create `tests/unit/__init__.py` package marker
- [ ] **T1.7** Create `tests/integration/__init__.py` package marker
- [ ] **T1.8** Create `tests/e2e/__init__.py` package marker
- [ ] **T1.9** Verify directory structure matches design.md

**Verification**: Run `python scripts/verify_package_structure.py`

---

### Task 2: Add pytest Configuration to pyproject.toml

- [ ] **T2.1** Add `[tool.pytest.ini_options]` section
- [ ] **T2.2** Configure `testpaths`, `python_files`, `python_functions`
- [ ] **T2.3** Add `addopts` for verbose output and strict markers
- [ ] **T2.4** Define test markers: `unit`, `integration`, `e2e`, `slow`, `network`, `mock`
- [ ] **T2.5** Add `[tool.coverage.run]` section with source and omit patterns
- [ ] **T2.6** Add `[tool.coverage.report]` section with exclude lines
- [ ] **T2.7** Verify pytest can discover tests: `pytest --collect-only`

**Verification**: Run `pytest --collect-only -q` and verify test collection

---

### Task 3: Create conftest.py with Fixtures

- [ ] **T3.1** Create `tests/conftest.py` with project root path setup
- [ ] **T3.2** Add `sample_config` fixture for test configuration
- [ ] **T3.3** Add `mock_env_vars` fixture using monkeypatch
- [ ] **T3.4** Add `temp_config_file` fixture for YAML config testing
- [ ] **T3.5** Add `mock_model` fixture for model objects
- [ ] **T3.6** Add `model_list` fixture for multiple models
- [ ] **T3.7** Add `mock_http_response` fixture for HTTP responses
- [ ] **T3.8** Add `mock_http_client` fixture
- [ ] **T3.9** Add `cache_config` fixture
- [ ] **T3.10** Add `reset_singletons` fixture for cleanup
- [ ] **T3.11** Add `reset_module_state` autouse fixture
- [ ] **T3.12** Verify fixtures are loaded: `pytest --fixtures`

**Verification**: Run `pytest --fixtures | grep -E "sample_config|mock_model"` to verify fixtures exist

---

### Task 4: Set Up Mocking Dependencies

- [ ] **T4.1** Install test dependencies: `pip install pytest pytest-cov pytest-xdist pytest-mock`
- [ ] **T4.2** Install additional mocking libraries: `pip install responses freezegun`
- [ ] **T4.3** Add dependencies to `pyproject.toml` or `requirements-test.txt`
- [ ] **T4.4** Verify imports work in test environment

**Verification**: Run `python -c "import pytest; import responses; import freezegun"`

---

## Phase 2: Unit Tests

### Task 5: Implement Routing Logic Tests

- [ ] **T5.1** Create `tests/unit/test_routing.py`
- [ ] **T5.2** Implement `test_routing_selects_lowest_utilization_model` (AC-12)
- [ ] **T5.3** Implement `test_routing_equal_utilization_round_robin` (AC-13)
- [ ] **T5.4** Implement `test_routing_empty_model_list` 
- [ ] **T5.5** Implement `test_routing_single_model`
- [ ] **T5.6** Implement `test_routing_model_factory`
- [ ] **T5.7** Implement `test_routing_updates_utilization`
- [ ] **T5.8** Implement `test_routing_filters_unavailable_models`
- [ ] **T5.9** Add `@pytest.mark.unit` markers to all tests

**Verification**: Run `pytest tests/unit/test_routing.py -v`

---

### Task 6: Implement Configuration Loading Tests

- [ ] **T6.1** Create `tests/unit/test_config.py`
- [ ] **T6.2** Implement `test_config_cli_args_override_env` (AC-7)
- [ ] **T6.3** Implement `test_config_env_vars_override_yaml` (AC-8)
- [ ] **T6.4** Implement `test_config_yaml_defaults` (AC-9)
- [ ] **T6.5** Implement `test_config_missing_yaml_file` 
- [ ] **T6.6** Implement `test_config_invalid_yaml_format`
- [ ] **T6.7** Implement `test_config_parse_model_list`
- [ ] **T6.8** Implement `test_config_parse_routing_params`
- [ ] **T6.9** Implement `test_config_env_var_prefix`
- [ ] **T6.10** Implement `test_config_missing_required_field` (AC-10)
- [ ] **T6.11** Implement `test_config_type_coercion`
- [ ] **T6.12** Add `@pytest.mark.unit` markers to all tests

**Verification**: Run `pytest tests/unit/test_config.py -v`

---

### Task 7: Implement Cache Behavior Tests

- [ ] **T7.1** Create `tests/unit/test_cache.py`
- [ ] **T7.2** Implement `test_cache_ttl_expiration`
- [ ] **T7.3** Implement `test_cache_get_returns_cached`
- [ ] **T7.4** Implement `test_cache_get_returns_none_for_expired`
- [ ] **T7.5** Implement `test_cache_set_updates_existing`
- [ ] **T7.6** Implement `test_cache_thread_safety`
- [ ] **T7.7** Implement `test_cache_max_size_eviction`
- [ ] **T7.8** Implement `test_cache_clear`
- [ ] **T7.9** Implement `test_cache_delete`
- [ ] **T7.10** Add `@pytest.mark.unit` markers to all tests

**Verification**: Run `pytest tests/unit/test_cache.py -v`

---

### Task 8: Implement API Client Tests

- [ ] **T8.1** Create `tests/unit/test_api_client.py`
- [ ] **T8.2** Implement `test_api_client_get_request`
- [ ] **T8.3** Implement `test_api_client_post_request`
- [ ] **T8.4** Implement `test_api_client_retry_on_5xx`
- [ ] **T8.5** Implement `test_api_client_no_retry_on_4xx`
- [ ] **T8.6** Implement `test_api_client_timeout`
- [ ] **T8.7** Implement `test_api_client_connection_error`
- [ ] **T8.8** Implement `test_api_client_rate_limit_handling`
- [ ] **T8.9** Add `@pytest.mark.unit` markers to all tests

**Verification**: Run `pytest tests/unit/test_api_client.py -v`

---

## Phase 3: Integration Tests

### Task 9: Implement Endpoint Tests

- [ ] **T9.1** Create `tests/integration/test_endpoints.py`
- [ ] **T9.2** Implement `test_health_endpoint_returns_200` (AC-15)
- [ ] **T9.3** Implement `test_health_endpoint_includes_models`
- [ ] **T9.4** Implement `test_chat_completions_basic` (AC-16)
- [ ] **T9.5** Implement `test_chat_completions_streaming`
- [ ] **T9.6** Implement `test_chat_completions_invalid_model` (AC-18)
- [ ] **T9.7** Implement `test_chat_completions_rate_limit`
- [ ] **T9.8** Implement `test_metrics_endpoint`
- [ ] **T9.9** Implement `test_model_list_endpoint` (AC-17)
- [ ] **T9.10** Add `@pytest.mark.integration` markers to all tests

**Verification**: Run `pytest tests/integration/test_endpoints.py -v`

---

### Task 10: Implement Config Loading Integration Tests

- [ ] **T10.1** Create `tests/integration/test_config_loading.py`
- [ ] **T10.2** Implement `test_config_hot_reload`
- [ ] **T10.3** Implement `test_config_invalid_reload`
- [ ] **T10.4** Implement `test_config_env_change_detected`
- [ ] **T10.5** Implement `test_config_multiple_sources` (AC-11)
- [ ] **T10.6** Implement `test_config_partial_override`
- [ ] **T10.7** Add `@pytest.mark.integration` markers to all tests

**Verification**: Run `pytest tests/integration/test_config_loading.py -v`

---

### Task 11: Implement Model Switching Tests

- [ ] **T11.1** Create `tests/integration/test_model_switching.py`
- [ ] **T11.2** Implement `test_model_failover_primary_to_secondary` (AC-14)
- [ ] **T11.3** Implement `test_model_failover_exhaustion`
- [ ] **T11.4** Implement `test_model_recovery`
- [ ] **T11.5** Add `@pytest.mark.integration` markers to all tests

**Verification**: Run `pytest tests/integration/test_model_switching.py -v`

---

## Phase 4: E2E Tests

### Task 12: Implement E2E Test Modules

- [ ] **T12.1** Create `tests/e2e/test_full_flows.py`
- [ ] **T12.2** Implement `test_e2e_basic_chat_flow`
- [ ] **T12.3** Implement `test_e2e_load_balancing`
- [ ] **T12.4** Implement `test_e2e_config_via_env`
- [ ] **T12.5** Implement `test_e2e_config_via_cli` (AC-1 to AC-6)
- [ ] **T12.6** Implement `test_e2e_graceful_shutdown`
- [ ] **T12.7** Implement `test_e2e_logging_output`
- [ ] **T12.8** Add `@pytest.mark.e2e` markers to all tests
- [ ] **T12.9** Add `@pytest.mark.slow` markers to appropriate tests

**Verification**: Run `pytest tests/e2e/test_full_flows.py -v`

---

## Phase 5: Verification Scripts

### Task 13: Create Verification Scripts

- [ ] **T13.1** Create `scripts/verify_package_structure.py`
  - [ ] Check tests/ directory exists
  - [ ] Check unit/integration/e2e subdirectories exist
  - [ ] Check conftest.py exists
  - [ ] Check pyproject.toml has pytest config
- [ ] **T13.2** Create `scripts/verify_no_hardcoded_models.py`
  - [ ] Search for 'moonshotai', 'zai-org', 'Qwen' patterns
  - [ ] Report file:line for each violation
- [ ] **T13.3** Create `scripts/verify_shell_scripts_deprecated.py`
  - [ ] Check for .sh files in tests/
  - [ ] Check for test-related scripts in scripts/
- [ ] **T13.4** Create `scripts/verify_python_equivalence.py`
  - [ ] Count test files
  - [ ] Count test functions using pytest --collect-only
  - [ ] Verify minimum thresholds

**Verification**: Run each script and verify exit code 0

---

### Task 14: Run All Tests and Verify

- [ ] **T14.1** Run all unit tests: `pytest tests/unit/ -v`
- [ ] **T14.2** Run all integration tests: `pytest tests/integration/ -v`
- [ ] **T14.3** Run all E2E tests: `pytest tests/e2e/ -v`
- [ ] **T14.4** Run with coverage: `pytest --cov=. --cov-report=term-missing`
- [ ] **T14.5** Verify code coverage >= 80%
- [ ] **T14.6** Run all verification scripts
- [ ] **T14.7** Verify all 18 acceptance criteria pass

**Verification**: 
- `pytest --cov=. --cov-report=term-missing --cov-fail-under=80`
- All verification scripts pass

---

### Task 15: Update Documentation

- [ ] **T15.1** Update `README.md` with testing instructions
- [ ] **T15.2** Add testing section to `AGENTS.md`
- [ ] **T15.3** Document how to run tests in `RUNNING-PROXY.md`
- [ ] **T15.4** Add CI/CD configuration for tests (if applicable)

**Verification**: Documentation files are updated and accurate

---

## Verification Summary

### Acceptance Criteria Checklist

| AC | Criterion | Task(s) | Verified |
|----|-----------|---------|----------|
| AC-1 | CLI accepts --host argument | T6.2, T12.5 | [ ] |
| AC-2 | CLI accepts --port argument | T6.2, T12.5 | [ ] |
| AC-3 | CLI accepts --config argument | T6.2, T12.5 | [ ] |
| AC-4 | CLI --help shows all options | T6.2 | [ ] |
| AC-5 | CLI validates port range | T6.2 | [ ] |
| AC-6 | CLI exits with code 0 on --version | T6.2 | [ ] |
| AC-7 | CLI args override ENV | T6.2 | [ ] |
| AC-8 | ENV vars override YAML | T6.3 | [ ] |
| AC-9 | YAML provides defaults | T6.3 | [ ] |
| AC-10 | Missing required fields error | T6.10 | [ ] |
| AC-11 | Invalid config format error | T6.6 | [ ] |
| AC-12 | Routes to lowest utilization | T5.2 | [ ] |
| AC-13 | Round-robin on equal | T5.3 | [ ] |
| AC-14 | Failover on unavailable | T11.2 | [ ] |
| AC-15 | /health returns 200 | T9.2 | [ ] |
| AC-16 | /v1/chat/completions works | T9.4 | [ ] |
| AC-17 | /v1/models returns list | T9.9 | [ ] |
| AC-18 | Invalid requests return errors | T9.6 | [ ] |

### Success Metrics

| Metric | Target | Actual | Verified |
|--------|--------|--------|----------|
| Code Coverage | >= 70% (80% after Phase 0) | | [ ] |
| Unit Tests | >= 30 | | [ ] |
| Integration Tests | >= 10 | | [ ] |
| E2E Tests | >= 5 | | [ ] |
| Total Tests | >= 54 | | [ ] |
| Acceptance Criteria | 18/18 | | [ ] |
| Verification Scripts | 4/4 | | [ ] |

---

## Dependencies

### Before Starting

- [ ] Python 3.11+ installed
- [ ] Project dependencies installed
- [ ] Access to project source code

### Parallel Tasks

Tasks in different phases can be worked on in parallel:
- Task 5 can run in parallel with Task 6, 7, 8
- Task 9 can run in parallel with Task 10, 11
- Task 13 can start after Task 1 is complete

---

## Notes

- Use Given-When-Then format in all test docstrings
- Each test should be independent and not depend on execution order
- Use fixtures for shared test data
- Mark tests appropriately with pytest markers
- Run verification scripts frequently during implementation
- Target 70% code coverage minimum (80% after Phase 0 refactoring)

---

## Completion Criteria

All tasks marked complete with verification checked off. The implementation is complete when:

1. All 54+ tests pass
2. Code coverage >= 70% (80% after Phase 0 refactoring)
3. All 4 verification scripts pass
4. All 18 acceptance criteria verified
5. Documentation updated
