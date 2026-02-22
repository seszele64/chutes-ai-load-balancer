# PROPOSAL: VDD Test Criteria for chutes-load-balancer

## Summary

This proposal introduces Verification-Driven Development (VDD) test criteria to transform the chutes-load-balancer project from a monolithic, shell-script-heavy codebase with hardcoded configurations into a well-tested, agent-friendly system with clear verification criteria.

## Problem Statement

### Current State

The chutes-load-balancer system currently suffers from several issues that impede maintainability, testability, and agent-driven development:

1. **Monolithic Code Structure**: The routing logic (`chutes_routing.py`) contains approximately 600+ lines of tightly coupled code handling routing decisions, config loading, caching, and API client behavior all in one module.

2. **Shell-Based Testing**: The project relies heavily on shell scripts in the `scripts/` directory for testing and validation. Shell scripts are:
   - Difficult to mock and test in isolation
   - Not agent-friendly for verification
   - Hard to maintain and debug
   - Platform-dependent

3. **Hardcoded Model Configurations**: The `litellm-config.yaml` and routing logic contain hardcoded model identifiers (e.g., "moonshotai", "zai-org", "Qwen") making it difficult to:
   - Add/remove models without code changes
   - Test different model configurations
   - Support dynamic model discovery

4. **Lack of Comprehensive Test Coverage**: No formal unit, integration, or E2E test framework exists, making it difficult to:
   - Verify correctness after changes
   - Enable CI/CD automation
   - Support refactoring safely

### Why VDD Approach

Verification-Driven Development (VDD) provides a test-first approach where:

1. **Verification Criteria Before Implementation**: Agents define success criteria as executable tests before writing implementation code
2. **Agent-Friendly Specifications**: Test cases serve as both documentation and executable verification
3. **Flexible Implementation**: Tests verify behavior, not implementation details, allowing agents freedom in how they achieve the criteria
4. **Quality Assurance**: Every feature change can be verified against defined test criteria

## Proposed Solution

### Test Framework Setup

Implement a comprehensive pytest-based testing framework with:

- **Unit Tests**: Test individual components in isolation (routing logic, config loading, caching, API client)
- **Integration Tests**: Test component interactions and API endpoints
- **E2E Tests**: Test complete user workflows

### Test Categories

| Category | Count | Purpose |
|----------|-------|---------|
| Unit Tests - Routing | 7 | Selection logic, equal utilization, edge cases |
| Unit Tests - Config | 10 | CLI/ENV/YAML precedence, parsing |
| Unit Tests - Cache | 8 | TTL, expiry, thread safety |
| Unit Tests - API Client | 7 | HTTP mocking, retries, errors |
| Integration Tests - Endpoints | 8 | /health, /v1/chat/completions |
| Integration Tests - Config | 5 | Config loading scenarios |
| Integration Tests - Model Switching | 3 | Failover behavior |
| E2E Tests | 6 | Full user flows |

### Acceptance Criteria Categories

1. **CLI Interface (AC-1 to AC-6)**: Command-line argument parsing, help output, validation
2. **Configuration Loading (AC-7 to AC-11)**: Precedence rules (CLI > ENV > YAML), error handling
3. **Routing Behavior (AC-12 to AC-14)**: Model selection, load balancing, failover
4. **Server Endpoints (AC-15 to AC-18)**: Health checks, completion endpoints

### Verification Scripts

Four standalone verification scripts to ensure code quality:

1. `verify_package_structure.py` - Validates test directory layout
2. `verify_no_hardcoded_models.py` - Ensures no hardcoded model names in source
3. `verify_shell_scripts_deprecated.py` - Confirms shell test scripts are removed
4. `verify_python_equivalence.py` - Validates Python tests provide equivalent coverage to shell scripts

## Benefits

### For Agents

- **Clear Success Criteria**: Each test case defines what "done" looks like
- **Independent Verification**: Agents can self-verify before submission
- **Flexible Implementation**: Tests verify behavior, not specific code patterns
- **Fast Feedback**: Unit tests run in milliseconds

### For Maintainers

- **Regression Prevention**: All changes verified against test suite
- **Documentation**: Test cases serve as executable specifications
- **CI/CD Ready**: Standard pytest workflow integrates with any CI system
- **Refactoring Safety**: Comprehensive tests enable safe code changes

### For System Quality

- **Code Coverage >= 80%**: Measurable quality metric
- **Zero Hardcoded Models**: Configuration-driven approach
- **Shell Script Deprecation**: Modern Python testing替代
- **Deterministic Testing**: No flaky shell-based tests

## Success Criteria for This Change

| Metric | Target | Measurement |
|--------|--------|-------------|
| Test Files Created | 15+ | File count in tests/ |
| Test Functions | 54+ | pytest --collect-only |
| Code Coverage | >= 70% (80% after Phase 0) | pytest --cov |
| Acceptance Criteria | 18/18 | All ACs pass |
| Verification Scripts | 4/4 | All scripts pass |
| Shell Scripts Deprecated | 100% | verify_shell_scripts_deprecated.py |
| Hardcoded Models | 0 | verify_no_hardcoded_models.py |

## Implementation Approach

### Phase 1: Infrastructure (Tasks 1-4)
- Create test directory structure
- Add pytest configuration
- Create conftest.py fixtures
- Set up mocking strategy

### Phase 2: Unit Tests (Tasks 5-8)
- Implement routing logic tests
- Implement config loading tests
- Implement cache behavior tests
- Implement API client tests

### Phase 3: Integration Tests (Tasks 9-11)
- Implement endpoint tests
- Implement config loading integration tests
- Implement model switching tests

### Phase 4: E2E Tests (Task 12)
- Implement full workflow tests

### Phase 5: Verification (Tasks 13-15)
- Create verification scripts
- Run all tests
- Update documentation

## Dependencies

This change builds upon the following existing specifications:

- `openspec/specs/routing/spec.md` - Routing logic behavior
- `openspec/specs/proxy/spec.md` - LiteLLM proxy configuration

No new specifications required - this change defines test criteria for existing functionality.

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| Test implementation complexity | Start with simple unit tests, progress to complex scenarios |
| Mocking challenges | Use pytest-mock and responses libraries |
| Coverage target may be unreachable | Adjust target if needed based on code analysis |
| Integration test flakiness | Use mocking for external dependencies |

## Timeline Estimate

- **Infrastructure**: 1 task
- **Unit Tests**: 4 tasks
- **Integration Tests**: 3 tasks
- **E2E Tests**: 1 task
- **Verification**: 3 tasks
- **Total**: 12 tasks

## Conclusion

This VDD test criteria change will transform the chutes-load-balancer into a well-tested, maintainable system that supports agent-driven development and provides clear verification criteria for all future changes. The investment in comprehensive testing will pay dividends in reduced bugs, faster iteration, and confident refactoring.
