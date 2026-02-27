# Change Proposal: API Structured Responses

## Problem Statement

The intelligent routing implementation in `src/litellm_proxy/routing/intelligent.py` currently returns `None` in at least six locations when routing fails or encounters errors:

| Location | Line | Scenario |
|----------|------|----------|
| `async_get_available_deployment` | 379 | No model list available for routing |
| `async_get_available_deployment` | 427 | Error fetching metrics from API |
| `async_get_available_deployment` | 429 | No chute metrics available |
| `async_get_available_deployment` | 433 | General exception handler |
| `get_available_deployment` (sync) | 451 | No model list available for routing |
| `get_available_deployment` (sync) | 494 | Error fetching metrics from API |
| `get_available_deployment` (sync) | 500 | General exception handler |

This behavior causes several critical issues:

1. **Downstream Consumer Failure**: LiteLLM's router expects a deployment dictionary or an exception, not `None`. Returning `None` causes cascading failures in the proxy layer.

2. **Silent Failures**: Returning `None` provides no diagnostic information. Logs may show warnings, but API consumers receive no structured feedback about what went wrong.

3. **No Degradation Path**: When metrics are unavailable (API timeout, rate limiting), the system returns `None` instead of attempting graceful degradation using cached data or fallback strategies.

4. **Inconsistent API Surface**: Different error scenarios produce different behaviors (some raise exceptions, some return `None`), making it difficult for consumers to handle errors uniformly.

## Proposed Solution

Implement structured error responses following these principles:

### 1. Never Return None

All routing methods must either:
- Return a valid deployment dictionary, OR
- Raise a specific exception for complete failures

Remove all `return None` statements from the routing logic.

### 2. Graceful Degradation Levels

Implement a tiered degradation strategy:

| Level | Condition | Behavior |
|-------|-----------|----------|
| **Level 1** | Cached metrics available | Use cached data for routing decisions |
| **Level 2** | Utilization data available | Fall back to utilization-only routing |
| **Level 3** | No metrics | Random selection with explicit warning |
| **Level 4** | Complete failure | Raise structured exception |

### 3. API-Level Circuit Breaker

LiteLLM already provides model-level circuit breakers. Add an API-level circuit breaker for Chutes API calls:

- Track consecutive failures (timeout, connection error)
- After threshold (default: 3), skip API calls for cooldown period (default: 30s)
- Return degraded responses during circuit open state
- Log state transitions for observability

### 4. Hybrid HTTP Status Codes

Use HTTP status codes to communicate degradation level:

| Status | Meaning |
|--------|---------|
| **200 OK** | Successful routing (full or degraded) |
| **503 Service Unavailable** | Complete failure - no degraded options available |

Note: This applies to the proxy's `/chat/completions` endpoint response format, not the routing method return value.

### 5. RFC 9457 Problem Details + OpenAI Error Format

Implement dual-format error responses:

**RFC 9457 Problem Details** (for HTTP-level errors):
```json
{
  "type": "https://api.chutes.ai/problems/routing-failure",
  "title": "Routing Failed",
  "status": 503,
  "detail": "All chutes unavailable after degradation cascade",
  "instance": "/v1/chat/completions"
}
```

**OpenAI-Compatible Error** (for compatibility):
```json
{
  "error": {
    "message": "All chutes unavailable after degradation cascade",
    "type": "server_error",
    "code": "routing_failure",
    "param": null
  }
}
```

## Scope

### In Scope
- [ ] Refactor `IntelligentMultiMetricRouting` to never return `None`
- [ ] Implement graceful degradation cascade (cached → utilization → random → exception)
- [ ] Add API-level circuit breaker for Chutes API calls
- [ ] Create structured response types for routing decisions
- [ ] Implement RFC 9457 Problem Details error format
- [ ] Maintain OpenAI-compatible error format
- [ ] Add hybrid HTTP status handling (200 for degraded, 503 for failure)
- [ ] Update tests to verify structured responses

### Out of Scope
- Changes to LiteLLM's internal routing framework
- Node-level circuit breaking (chute-level only)
- Client-side error handling modifications
- Metrics storage or persistence layer changes

## Success Criteria

### Functional Requirements
- [ ] No `return None` statements in routing methods
- [ ] All error scenarios produce structured responses
- [ ] Graceful degradation works through all 4 levels
- [ ] Circuit breaker opens after threshold failures
- [ ] Circuit breaker closes after cooldown period
- [ ] RFC 9457 Problem Details format is valid
- [ ] OpenAI-compatible errors remain functional

### Testable Scenarios
1. **API Timeout**: Returns cached data or utilization-only routing
2. **No Model List**: Raises `EmptyModelListError` with structured details
3. **All Circuits Open**: Returns 503 with Problem Details
4. **Partial Data**: Uses available metrics for routing
5. **Random Fallback**: Includes warning in response

### Performance Targets
- Circuit breaker state check: <1ms
- Degradation level determination: <5ms
- Error response serialization: <2ms

## Impact

### Files to Modify

| File | Changes |
|------|---------|
| `src/litellm_proxy/routing/intelligent.py` | Replace `return None` with structured responses, add circuit breaker, implement degradation cascade |
| `src/litellm_proxy/api/client.py` | Add circuit breaker state tracking, structured error responses |
| `src/litellm_proxy/exceptions.py` | Add new exception types for routing failures |
| `src/litellm_proxy/__init__.py` | Export new exception types |

### New Files to Create

| File | Purpose |
|------|---------|
| `src/litellm_proxy/routing/responses.py` | Structured response types for routing decisions |
| `src/litellm_proxy/routing/circuit_breaker.py` | API-level circuit breaker implementation |

### Consumer Impact

- **Existing consumers** using `LiteLLM` directly: No changes required - exceptions will propagate
- **Direct API consumers**: Will receive structured errors instead of `None` or silent failures
- **Monitoring/observability**: Improved error diagnostics with Problem Details

## Risks

1. **Breaking Change**: Some consumers may depend on `None` return values. Mitigate by providing migration guide and deprecation period.

2. **Circuit Breaker State**: Distributed state across instances may cause inconsistent behavior. Mitigate by using consistent hashing for instance selection.

3. **Performance Overhead**: Circuit breaker checks add latency. Mitigate with in-memory state and fast-path optimizations.

4. **Error Response Size**: RFC 9457 responses are larger than `None`. Acceptable trade-off for better diagnostics.

## Rollback Plan

If issues arise:

1. Revert to previous behavior by setting feature flag `USE_STRUCTURED_RESPONSES=false`
2. Fall back to exception-only model (no graceful degradation)
3. Disable circuit breaker via `CIRCUIT_BREAKER_ENABLED=false`

## Dependencies

### External Dependencies
- Chutes API endpoints:
  - `/chutes/utilization` - Utilization data
  - `/invocations/stats/llm` - LLM statistics (TPS, TTFT)
- LiteLLM proxy (http://localhost:4000)

### Internal Dependencies
- `IntelligentMultiMetricRouting` class
- `ChutesAPIClient` class
- Existing exception hierarchy

## Timeline Estimate

| Phase | Effort |
|-------|--------|
| Design & Specification | 2 hours |
| Implementation | 4 hours |
| Testing | 2 hours |
| Documentation | 1 hour |
| **Total** | **9 hours**
