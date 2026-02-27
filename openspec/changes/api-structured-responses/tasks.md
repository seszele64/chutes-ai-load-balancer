# Tasks: API Structured Responses

## Change Summary
Replace all `None` returns in `intelligent.py` with structured responses, implement circuit breakers, graceful degradation, and standardized error formats.

**Proposal**: [proposal.md](./proposal.md)
**Design**: _To be created based on these tasks_

---

## P0 - Critical (Fix None Returns)

### Task P0-1: Replace None return at line 379 (async_get_available_deployment - No model list)
- [x] **Location**: `src/litellm_proxy/routing/intelligent.py:379`
- **Current behavior**: Returns `None` when no model list is available
- **New behavior**: Raise `EmptyModelListError` exception with structured details
- **Acceptance criteria**:
  - [x] Exception includes message: "No model list available for routing"
  - [x] Exception includes request context (model name, timestamp)
  - [x] Test verifies exception is raised

### Task P0-2: Replace None return at line 427 (async_get_available_deployment - API error)
- [x] **Location**: `src/litellm_proxy/routing/intelligent.py:427`
- **Current behavior**: Returns `None` when API fetch fails
- **New behavior**: Trigger degradation level 1 (cached fallback) or raise exception
- **Acceptance criteria**:
  - [x] Falls back to cached metrics if available
  - [x] Logs warning about API failure with error details
  - [x] Returns valid deployment if cached data exists
  - [x] Continues to next degradation level if no cache

### Task P0-3: Replace None return at line 429 (async_get_available_deployment - No chute metrics)
- [x] **Location**: `src/litellm_proxy/routing/intelligent.py:429`
- **Current behavior**: Returns `None` when no chute metrics available
- **New behavior**: Trigger degradation level 2 (utilization-only routing)
- **Acceptance criteria**:
  - [x] Attempts utilization-only routing as fallback
  - [x] Uses available utilization data for selection
  - [x] Logs warning about partial metrics

### Task P0-4: Replace None return at line 433 (async_get_available_deployment - General exception)
- [x] **Location**: `src/litellm_proxy/routing/intelligent.py:433`
- **Current behavior**: Returns `None` for any unhandled exception
- **New behavior**: Raise `RoutingError` exception with full error context
- **Acceptance criteria**:
  - [x] Exception includes original error message
  - [x] Exception includes stack trace for debugging
  - [x] Exception type is specific (not generic Exception)

### Task P0-5: Replace None return at line 451 (get_available_deployment sync - No model list)
- [x] **Location**: `src/litellm_proxy/routing/intelligent.py:451`
- **Current behavior**: Returns `None` when no model list is available (sync version)
- **New behavior**: Raise `EmptyModelListError` exception (same as P0-1)
- **Acceptance criteria**:
  - [x] Uses same exception class as async version
  - [x] Includes same context information

### Task P0-6: Replace None return at line 494 (get_available_deployment sync - API error)
- [x] **Location**: `src/litellm_proxy/routing/intelligent.py:494`
- **Current behavior**: Returns `None` when API fetch fails (sync version)
- **New behavior**: Same degradation logic as P0-2
- **Acceptance criteria**:
  - [x] Same fallback behavior as async version
  - [x] Consistent logging format

### Task P0-7: Replace None return at line 500 (get_available_deployment sync - General exception)
- [x] **Location**: `src/litellm_proxy/routing/intelligent.py:500`
- **Current behavior**: Returns `None` for any unhandled exception (sync version)
- **New behavior**: Raise `RoutingError` exception (same as P0-4)
- **Acceptance criteria**:
  - [x] Uses same exception class as async version
  - [x] Consistent error context

---

## P1 - High Priority

### Task P1-1: Implement circuit breaker for Chutes API calls
- [x] **New file**: `src/litellm_proxy/routing/circuit_breaker.py`
- **Description**: Create API-level circuit breaker for Chutes API calls
- **Acceptance criteria**:
  - [x] Tracks consecutive failures (configurable threshold, default: 3)
  - [x] After threshold, enters "open" state for cooldown period (default: 30s)
  - [x] Returns degraded responses during open state
  - [x] Logs state transitions (closed → open → half-open → closed)
  - [x] Circuit state check adds <1ms latency
  - [x] Thread-safe state management

### Task P1-2: Implement graceful degradation levels
- [x] **Description**: Implement 4-tier degradation cascade
- **Acceptance criteria**:
  - [x] **Level 1 (Cache)**: Use cached metrics if available - returns deployment with `degradation_level=1`
  - [x] **Level 2 (Utilization)**: Fall back to utilization-only routing if TPS/TTFT unavailable - returns deployment with `degradation_level=2`
  - [x] **Level 3 (Random)**: Random selection with explicit warning if no metrics - returns deployment with `degradation_level=3`
  - [x] **Level 4 (Failure)**: Raise structured exception if all options exhausted - raises `RoutingError` with `degradation_level=4`
  - [x] Each level includes appropriate logging
  - [x] Degradation level is tracked in response metadata

### Task P1-3: Add hybrid HTTP status codes
- [x] **Location**: `src/litellm_proxy/api/routes.py` (FastAPI routes)
- **Description**: Return appropriate HTTP status codes based on degradation level
- **Acceptance criteria**:
  - [x] 200 OK for successful routing (any degradation level 1-3)
  - [x] 503 Service Unavailable for complete failure (degradation level 4)
  - [x] Response includes `X-Degradation-Level` header
  - [x] Response body includes structured error for 503

---

## P2 - Medium Priority

### Task P2-1: Implement RFC 9457 Problem Details error format
- [x] **New file**: `src/litellm_proxy/routing/responses.py`
- **Description**: Create structured response types for RFC 9457 compliance
- **Acceptance criteria**:
  - [x] Response includes `type` URL (e.g., `https://api.chutes.ai/problems/routing-failure`)
  - [x] Response includes `title` (e.g., "Routing Failed")
  - [x] Response includes `status` (HTTP status code)
  - [x] Response includes `detail` (human-readable error message)
  - [x] Response includes `instance` (request path)
  - [x] Response is valid JSON

### Task P2-2: Implement OpenAI-compatible error format
- [x] **Location**: `src/litellm_proxy/routing/responses.py`
- **Description**: Maintain backward compatibility with OpenAI error format
- **Acceptance criteria**:
  - [x] Response includes `error` object at root level
  - [x] `error.message` contains human-readable message
  - [x] `error.type` contains error type (e.g., `server_error`, `invalid_request_error`)
  - [x] `error.code` contains error code (e.g., `routing_failure`)
  - [x] `error.param` is null for general errors
  - [x] Format matches OpenAI API error responses

### Task P2-3: Add response metadata (routing_info, degradation_level)
- [x] **Description**: Include routing metadata in successful responses
- **Acceptance criteria**:
  - [x] Response includes `routing_info` object with:
    - [x] `selected_chute` - ID of selected chute
    - [x] `selection_reason` - Explanation of why this chute was selected
    - [x] `metrics_used` - List of metrics considered
  - [x] Response includes `degradation_level` (1-4)
  - [x] Metadata is included in both successful and degraded responses
  - [x] Metadata is logged for observability

---

## P3 - Nice to Have

### Task P3-1: Add Prometheus metrics endpoint
- [x] **Location**: New endpoint in `src/litellm_proxy/api/routes.py`
- **Description**: Expose circuit breaker and routing metrics for Prometheus
- **Acceptance criteria**:
  - [x] Endpoint at `/metrics` (or `/prometheus`)
  - [x] Metrics include:
    - [x] `chutes_routing_requests_total` - Total routing requests
    - [x] `chutes_routing_degradation_level` - Current degradation level distribution
    - [x] `chutes_circuit_breaker_state` - Circuit breaker state (0=closed, 1=open, 2=half-open)
    - [x] `chutes_circuit_breaker_failures_total` - Total consecutive failures
  - [x] Metrics follow Prometheus naming conventions
  - [x] Metrics include relevant labels (chute_id, error_type)

### Task P3-2: Add /health endpoint with routing status
- [x] **Location**: New endpoint in `src/litellm_proxy/api/routes.py`
- [x] **Description**: Health check endpoint that includes routing subsystem status
- **Acceptance criteria**:
  - [x] Endpoint at `/health` or `/health/routing`
  - [x] Response includes:
    - [x] `status` - "healthy", "degraded", or "unhealthy"
    - [x] `circuit_breaker_state` - Current state
    - [x] `last_successful_request` - Timestamp
    - [x] `consecutive_failures` - Current failure count
    - [x] `degradation_level` - Current system degradation
  - [x] Response includes HTTP status appropriate to health

### Task P3-3: Add request tracing
- [x] **Description**: Add distributed tracing for routing decisions
- **Acceptance criteria**:
  - [x] Trace includes request ID
  - [x] Trace includes routing decision path (which degradation levels were tried)
  - [x] Trace includes timing for each step
  - [x] Trace is logged with routing decisions
  - [x] Compatible with OpenTelemetry if available

---

## Implementation Order

```
1. P0-1 through P0-7 (Critical - Fix None returns)
   └─ Requires: New exception types in exceptions.py

2. P1-1 (Circuit breaker)
   └─ Requires: P0 tasks complete

3. P1-2 (Graceful degradation)
   └─ Requires: P1-1 (circuit breaker)

4. P1-3 (HTTP status codes)
   └─ Requires: P1-2 (degradation levels)

5. P2-1, P2-2, P2-3 (Response formats)
   └─ Requires: P1 tasks complete

6. P3-* (Observability)
   └─ Independent, can run in parallel
```

---

## Dependencies

### Files to Modify
| File | Tasks |
|------|-------|
| `src/litellm_proxy/routing/intelligent.py` | P0-1 through P0-7 |
| `src/litellm_proxy/exceptions.py` | P0 tasks (add new exceptions) |
| `src/litellm_proxy/api/` (FastAPI routes) | P1-3, P2-1, P2-2, P3-2 |

### New Files to Create
| File | Tasks |
|------|-------|
| `src/litellm_proxy/routing/circuit_breaker.py` | P1-1 |
| `src/litellm_proxy/routing/responses.py` | P2-1, P2-2, P2-3 |

---

## Verification Checklist

Before marking tasks complete, verify:

- [x] All `return None` statements removed from `intelligent.py`
- [x] Tests pass for each degradation level scenario
- [x] Circuit breaker opens after threshold failures
- [x] Circuit breaker closes after cooldown
- [x] RFC 9457 format validates against schema
- [x] OpenAI format matches specification
- [x] HTTP status codes are correct for each scenario
- [x] Response metadata is present and accurate
- [x] Performance targets met (<1ms circuit check, <5ms degradation, <2ms serialization)

---

## Related Artifacts

- **Proposal**: [proposal.md](./proposal.md)
- **Design**: _Create design.md with detailed technical specifications_
- **Tests**: Add tests in `tests/` for each degradation level
- **Master Spec**: Update `openspec/specs/routing/spec.md` after implementation

---

## Implementation Summary

### Completed
- All P0, P1, P2, and P3 tasks
- 16/16 tasks complete (100%)
- 4 new files created
- 4 files modified
- 23 new tests added
