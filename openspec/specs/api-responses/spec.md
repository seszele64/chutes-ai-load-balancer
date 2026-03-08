# API Structured Responses

## Summary

This document defines the technical specifications for implementing structured API responses in the chutes-load-balancer system. The specifications cover error response formats, HTTP status code strategies, graceful degradation levels, circuit breaker configuration, response schemas, and API endpoint behaviors.

---

## Requirements

### Requirement: RFC 9457 Problem Details Error Format

All HTTP-level errors MUST return a Problem Details response as defined in [RFC 9457](https://www.rfc-editor.org/rfc/rfc9457).

#### Scenario: Successful Error Response Format

**GIVEN** a request that results in an HTTP error  
**WHEN** the proxy returns an error response  
**THEN** the response SHALL include a `problem` object with:
- `type`: URI reference identifying the problem type
- `title`: Short human-readable summary
- `status`: HTTP status code (400-599)
- `detail`: Human-readable explanation
- `instance`: URI reference for this occurrence
- `extensions`: Additional problem details

**AND** the response headers SHALL include:
- `Content-Type: application/problem+json`
- `X-Content-Type-Options: nosniff`

---

### Requirement: OpenAI-Compatible Error Format

All error responses MUST also include an OpenAI-compatible error format for backward compatibility with existing consumers.

#### Scenario: Combined Response Format

**GIVEN** a request that results in an error  
**WHEN** the proxy returns the error response  
**THEN** the response SHALL include both:
1. A `problem` object with RFC 9457 Problem Details
2. An `error` object with OpenAI-compatible format

**AND** the `error` object SHALL contain:
- `message`: Human-readable error message
- `type`: Error type (invalid_request_error, authentication_error, etc.)
- `code`: Specific error code
- `param`: Parameter that caused the error (if applicable)
- `degradation_level`: Degradation level if applicable (1-4)

---

### Requirement: HTTP Status Code Selection

The proxy SHALL use appropriate HTTP status codes based on the routing outcome.

#### Scenario: 200 OK for Successful Routing

**GIVEN** a request to the LiteLLM proxy endpoint  
**WHEN** the routing logic succeeds at any degradation level (0-3)  
**THEN** the response SHALL return HTTP 200 OK

**AND** the `X-Degradation-Level` header SHALL be set:
- `0`: Full success - all metrics available
- `1`: Cached data used
- `2`: Utilization-only routing
- `3`: Random selection with warning

#### Scenario: 503 Service Unavailable for Complete Failure

**GIVEN** a request to the LiteLLM proxy endpoint  
**WHEN** Degradation Level 4 is reached (complete failure)  
**OR** circuit breaker is open with no cached data  
**OR** all chutes are unavailable  
**THEN** the response SHALL return HTTP 503 Service Unavailable

#### Scenario: 500 Internal Server Error for Unexpected Errors

**GIVEN** a request to the LiteLLM proxy endpoint  
**WHEN** an unexpected exception occurs that cannot be classified  
**OR** an internal error not related to routing occurs  
**THEN** the response SHALL return HTTP 500 Internal Server Error

---

### Requirement: Graceful Degradation Levels

The system SHALL implement graceful degradation levels to maintain availability when metrics are unavailable.

#### Scenario: Level 0 - Full Success

**GIVEN** all chute metrics are available (utilization, TPS, TTFT)  
**WHEN** the routing logic executes  
**THEN**:
- Calculate weighted scores using all available metrics
- Return deployment with highest composite score
- Set `X-Degradation-Level: 0` header
- Log at INFO level with full metrics

#### Scenario: Level 1 - Cached Data

**GIVEN** fresh cached metrics are available (cache age < 60 seconds)  
**WHEN** the API calls fail (timeout, rate limit, connection error)  
**THEN**:
- Use cached metrics for routing decisions
- Return deployment with highest cached score
- Set `X-Degradation-Level: 1` header
- Include `X-Cache-Age-Seconds` header
- Log at WARNING level with cache age

#### Scenario: Level 2 - Utilization Only

**GIVEN** only utilization data is available (TPS, TTFT unavailable)  
**WHEN** the stats API fails but utilization API succeeds  
**THEN**:
- Calculate scores using utilization metrics only (weight: utilization=0.7, latency=0.3)
- Return deployment with highest utilization score
- Set `X-Degradation-Level: 2` header
- Include warning in response:
  ```json
  {"warning": "Using degraded routing - TPS/TTFT metrics unavailable", "degradation_level": 2}
  ```

#### Scenario: Level 3 - Random Fallback

**GIVEN** no metrics are available (API failures + no cache)  
**WHEN** all metric sources fail  
**THEN**:
- Select random available deployment
- Set `X-Degradation-Level: 3` header
- Include warning in response:
  ```json
  {"warning": "Random deployment selection - all metrics unavailable", "degradation_level": 3, "available_models": [...]}
  ```
- Log at ERROR level

#### Scenario: Level 4 - Complete Failure

**GIVEN** no deployment can be selected  
**WHEN**:
- Model list is empty
- All chutes are marked unavailable
- Circuit breaker is open with no cached data  
**THEN**:
- Raise `RoutingFailureException`
- Return HTTP 503
- Include full problem details in response
- Log at CRITICAL level

---

### Requirement: Circuit Breaker Implementation

The system SHALL implement a circuit breaker pattern to prevent cascading failures.

#### Scenario: Circuit Breaker Closed State

**GIVEN** the circuit breaker is in CLOSED state  
**WHEN** a request to the Chutes API succeeds  
**THEN**:
- Reset failure counter to 0
- Update last success timestamp
- Allow request to proceed normally

**GIVEN** the circuit breaker is in CLOSED state  
**WHEN** a request to the Chutes API fails (timeout, 5xx, connection error)  
**THEN**:
- Increment failure counter by 1
- Log the failure at WARNING level
- Update last failure timestamp
- IF failure counter >= failure_threshold:
  - Transition to OPEN state
  - Log at ERROR level
  - Set open timestamp

#### Scenario: Circuit Breaker Open State

**GIVEN** the circuit breaker is in OPEN state  
**WHEN** a request is made to the Chutes API  
**THEN**:
- Check if (current_time - open_timestamp) >= timeout_seconds
- IF timeout elapsed:
  - Transition to HALF-OPEN state
  - Log at INFO level
  - Allow request to proceed
- ELSE:
  - Fail fast - return degraded response immediately
  - Include circuit breaker state in response

#### Scenario: Circuit Breaker Half-Open State

**GIVEN** the circuit breaker is in HALF-OPEN state  
**WHEN** a request to the Chutes API succeeds  
**THEN**:
- Increment success counter by 1
- IF success counter >= success_threshold:
  - Transition to CLOSED state
  - Reset failure and success counters
  - Log at INFO level

**GIVEN** the circuit breaker is in HALF-OPEN state  
**WHEN** a request to the Chutes API fails  
**THEN**:
- Transition back to OPEN state
- Log at WARNING level
- Reset success counter
- Set open timestamp

---

### Requirement: Response Schema Definitions

The system SHALL define and validate response schemas for all API responses.

#### Scenario: Routing Decision Response Schema

**GIVEN** a successful routing decision  
**WHEN** the response is generated  
**THEN** the response SHALL conform to the RoutingDecision schema:
- `deployment`: Selected deployment (model, deployment_id, api_base)
- `degradation_level`: Current level (0-3)
- `timestamp`: ISO 8601 datetime
- `metrics_used`: Which metrics were used for routing
- `cache_info`: Cache usage information (if applicable)
- `warning`: Warning message if degraded

#### Scenario: Error Response Schema

**GIVEN** an error response  
**WHEN** the response is generated  
**THEN** the response SHALL conform to the StructuredError schema:
- `problem`: RFC 9457 Problem Details object
- `error`: OpenAI-compatible error object
- Both objects SHALL be included in the same response

#### Scenario: Health Check Response Schema

**GIVEN** a request to the health endpoint  
**WHEN** the health check is generated  
**THEN** the response SHALL conform to the HealthCheck schema:
- `status`: healthy/degraded/unhealthy
- `circuit_breaker`: Current circuit breaker state
- `degradation_available`: Which degradation strategies are available
- `available_models`: List of available models

---

### Requirement: API Endpoint Specifications

The system SHALL implement all specified API endpoints with defined behaviors.

#### Scenario: POST /v1/chat/completions Success

**GIVEN** a POST request to `/v1/chat/completions`  
**WHEN** the request is valid and models are available  
**THEN**:
- Execute intelligent routing with degradation support
- Return 200 OK with chat completion response
- Include `X-Degradation-Level` header
- If degradation > 0, include warning in response metadata

#### Scenario: POST /v1/chat/completions Failure

**GIVEN** a POST request to `/v1/chat/completions`  
**WHEN** routing fails at all degradation levels  
**THEN**:
- Return 503 Service Unavailable
- Include Problem Details in response body
- Include OpenAI-compatible error in response body
- Log at CRITICAL level

#### Scenario: POST /v1/chat/completions with Circuit Breaker Open

**GIVEN** a POST request to `/v1/chat/completions`  
**WHEN** circuit breaker is open  
**THEN**:
- Return degraded response using cached data if available
- If no cache, return 503 with Problem Details
- Include `X-Circuit-Breaker-State: open` header

#### Scenario: GET /v1/models

**GIVEN** a GET request to `/v1/models`  
**WHEN** the system is operational  
**THEN**:
- Return list of available models from configuration
- Include degradation status in response
- Return 200 OK

**GIVEN** a GET request to `/v1/models`  
**WHEN** circuit breaker is open  
**THEN**:
- Return 200 OK with cached model list if available
- Include warning about degraded state
- Set `X-Circuit-Breaker-State: open` header

#### Scenario: GET /health

**GIVEN** a GET request to `/health`  
**WHEN** called  
**THEN**:
- Return current health status
- Include circuit breaker state
- Include degradation availability status
- Return 200 OK even if degraded

#### Scenario: GET /metrics

**GIVEN** a GET request to `/metrics`  
**WHEN** called  
**THEN**:
- Return Prometheus-format metrics
- Include custom metrics:
  - `chutes_routing_degradation_level`
  - `chutes_circuit_breaker_state`
  - `chutes_routing_cache_hits_total`
  - `chutes_routing_cache_misses_total`
  - `chutes_api_failures_total`

---

### Requirement: Exception Hierarchy

The system SHALL implement a structured exception hierarchy for routing failures.

#### Scenario: Exception to HTTP Status Mapping

**GIVEN** any of the following exceptions are raised  
**WHEN** the exception is not handled at a lower level  
**THEN** the exception SHALL be mapped to the appropriate HTTP status:

| Exception | HTTP Status | Problem Type |
|-----------|-------------|--------------|
| `EmptyModelListError` | 503 | empty-model-list |
| `MetricsUnavailableError` | 503 | metrics-unavailable |
| `CircuitBreakerOpenError` | 503 | circuit-breaker-open |
| `DegradationExhaustedError` | 503 | routing-failure |
| `ValidationError` | 400 | validation-error |
| `AuthenticationError` | 401 | authentication-error |

---

### Requirement: Configuration Reference

The system SHALL support configuration via environment variables.

#### Scenario: Environment Variable Configuration

**GIVEN** the system is started  
**WHEN** environment variables are set  
**THEN** the following variables SHALL be supported:

| Variable | Default | Description |
|----------|---------|-------------|
| `USE_STRUCTURED_RESPONSES` | `true` | Enable structured response format |
| `CIRCUIT_BREAKER_ENABLED` | `true` | Enable circuit breaker |
| `CIRCUIT_BREAKER_FAILURE_THRESHOLD` | `3` | Failures before opening |
| `CIRCUIT_BREAKER_TIMEOUT_SECONDS` | `30` | Time before half-open |
| `CIRCUIT_BREAKER_SUCCESS_THRESHOLD` | `2` | Successes to close |
| `CACHE_TTL_SECONDS` | `60` | Cache time-to-live |
| `DEGRADATION_ENABLED` | `true` | Enable degradation levels |

---

### Requirement: Testing Requirements

The system SHALL meet the following testing requirements.

#### Scenario: Unit Test Coverage

**GIVEN** the implementation  
**WHEN** unit tests are run  
**THEN** the following SHALL be tested:
- Each degradation level transition
- Circuit breaker state transitions
- Exception hierarchy
- Response schema validation
- HTTP status code selection

#### Scenario: Integration Test Coverage

**GIVEN** the implementation  
**WHEN** integration tests are run  
**THEN** the following SHALL be tested:
- Full degradation cascade
- Circuit breaker with live API
- Error response format
- Health check endpoint

#### Scenario: Performance Requirements

**GIVEN** the implementation  
**WHEN** performance tests are run  
**THEN** the following thresholds SHALL be met:
- Circuit breaker check latency < 1ms
- Degradation determination < 5ms
- Error serialization < 2ms

---

## Related Documents

| Document | Location |
|----------|----------|
| Routing Spec | `openspec/specs/routing/spec.md` |
| Proxy Spec | `openspec/specs/proxy/spec.md` |
